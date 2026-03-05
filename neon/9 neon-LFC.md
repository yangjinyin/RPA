# 一：背景

在 Neon 的**存储分离架构**中，Compute Node和 Pageserver 是通过网络进行交互的。时延是一个影响性能的重要点。

LFC (local file cache) 层：在 Compute Node 本地磁盘上维护一个**透明的页面缓存层**，作为 Shared Buffer 和 Pageserver 之间的中间层。

**简单来说，LFC 逻辑就是：先看本地有没有，没有就去云端拿，拿回来顺手存一份。**

```c
PostgreSQL 访问路径:
1. Shared Buffer (内存，最快)
   ↓ miss
2. LFC (本地磁盘，次快)
   ↓ miss
3. Pageserver (网络+远程存储，最慢)
```



# 二：参数

| 参数                     | 说明                                       | 默认值 |
| ------------------------ | ------------------------------------------ | ------ |
| max_file_cache_size      | lfc的总大小，参数建议设成可用磁盘空间的70% | 1mb    |
| file_cache_chunk_size    | 一批次读取大小，默认读取1mb(128 * 8k)      | 128    |
| file_cache_prewarm_batch | 预热批量,越大越快但占用内存                | 128    |



# 三：核心设计

## 3.1 设计思想

1. **简单可靠**

   - 单一大文件存储所有页面，而非多文件（跟duckdb的设计思想一致）

   - 启动时完全重建元数据，无需担心一致性 （启动时通过`lfc_prewarm()`进行并行预热）
   - 任何错误立即禁用 LFC，不影响数据正确性

2. **高性能优先**

   - I/O 操作不持有锁
   - 批量读写（preadv/pwritev）（采用chunk读写，结合之前文章介绍的pg会将连续的IO请求合并）
   - 无锁快速路径（lfc_maybe_disabled）

3. **并发友好**

   - 状态机管理并发访问
   - Pin 机制防止竞态条件



## 3.2 核心数据结构

#### FileCacheEntry（缓存条目）

```c
typedef struct FileCacheEntry {
    BufferTag   key;          // 页面身份标识
    uint32      hash;         // 预计算的哈希值
    uint32      offset;       // 在缓存文件中的位置（chunk 编号）
    uint32      access_count; // Pin 计数（>0 时不能驱逐）
    dlist_node  list_node;    // LRU 链表节点
    uint32      state[];      // 每个块的状态（2 位/块）
}


```

**状态压缩技巧**：
每个块用 **2 位**表示 4 种状态：

- 00 (UNAVAILABLE) - 块不在缓存中
- 01 (AVAILABLE)   - 块可以直接使用
- 10 (PENDING)     - 块正在被读写
- 11 (REQUESTED)   - 有其他进程在等待此块

128 个块需要：128 × 2 = 256 位 = 32 字节。

```c++
状态机控制：
UNAVAILABLE  ──write──>  PENDING  ──complete──>  AVAILABLE
                            │                       │
                            │                       │
                        有人等待                 可以读写
                            ↓                       
                        REQUESTED
```



#### FileCacheControl（文件cache结构）

```c
typedef struct FileCacheControl {
    uint64      generation;   // 版本号（检测配置变更）
    uint32      size;         // 当前文件大小（chunks）
    uint32      used;         // 已使用的 chunks
    uint32      limit;        // 软限制（可动态调整）
    uint32      pinned;       // 被 pin 的 chunks
    
    dlist_head  lru;          // LRU 链表
    dlist_head  holes;        // 空洞链表（缩容时产生）
    
    ConditionVariable cv[64]; // 条件变量数组（用于状态同步）
    
    HyperLogLogState wss_estimation; // 工作集大小估算
    
    /* 统计信息 */
    uint64      hits, misses, writes;
    uint64      time_read, time_write;
}
```

## 3.3 文件布局

LFC 使用单一大文件存储所有页面

```c++
file.cache 文件布局:
┌─────────────┬─────────────┬─────────────┬─────────────┐
│  Chunk #0   │  Chunk #1   │  Chunk #2   │   Hole #3   │ ...
│  (1MB)      │  (1MB)      │  (1MB)      │  (punch)    │
├─────────────┼─────────────┼─────────────┼─────────────┤
│ Block 0-127 │ Block 0-127 │ Block 0-127 │   Empty     │
│ of Relation │ of Relation │ of Relation │             │
│    A        │      B      │      C      │             │
└─────────────┴─────────────┴─────────────┴─────────────┘

每个 Chunk = 128 blocks × 8KB = 1MB
```

**计算文件偏移 = （chunk_offset * 128 + block_offset） * 8KB**



## 3.4 写入流程

`lfc_writev`：将脏页批量写入LFC中。

**调用逻辑**

```c++
|-->FlushBuffer() //PG Buffer Manager模块 淘汰脏页
|	|-->smgrwrite() //SMGR层
|	|	|-->neon_write() //Neon存储管理器
|	|	|	|-->lfc_writev() //写入本地缓存
```

**主要逻辑**

```c++
void
lfc_writev(NRelFileInfo rinfo, ForkNumber forkNum, BlockNumber blkno,
		   const void *const *buffers, BlockNumber nblocks)
{
	BufferTag	tag;
	FileCacheEntry *entry;
	ssize_t		rc;
	bool		found;
	uint32		hash;
	uint64		generation;
	uint32		entry_offset;
	int			buf_offset = 0;
	
    //1. 检查开关
	if (lfc_maybe_disabled())	
		return;
    
    //2. 构造 BufferTag 并更新 Working Set 统计
	CopyNRelFileInfoToBufTag(tag, rinfo);
	CriticalAssert(BufTagGetRelNumber(&tag) != InvalidRelFileNumber);
	tag.forkNum = forkNum;

	for (int i = 0; i < nblocks; i++)
	{
		tag.blockNum = blkno + i;
		addSHLL(&lfc_ctl->wss_estimation, hash_bytes((uint8_t const*)&tag, sizeof(tag)));
	}
    
    //3. 获取全局排他锁
	LWLockAcquire(lfc_lock, LW_EXCLUSIVE);

	if (!LFC_ENABLED() || !lfc_ensure_opened())
	{
		LWLockRelease(lfc_lock);
		return;
	}
	generation = lfc_ctl->generation; //记录版本号

	//4. 主循环 - 分Chunk 处理
	while (nblocks > 0)
	{
		struct iovec iov[PG_IOV_MAX]; //向量化IO缓冲区
        
        // 4.1 计算当前 chunk 内的块数
		int		chunk_offs = BLOCK_TO_CHUNK_OFF(blkno);
		int		blocks_in_chunk = Min(nblocks, lfc_blocks_per_chunk - chunk_offs);
		instr_time io_start, io_end;
		ConditionVariable* cv;
        
		//4.2 构建 iovec（批量 I/O 准备）
		for (int i = 0; i < blocks_in_chunk; i++)
		{
			iov[i].iov_base = unconstify(void *, buffers[buf_offset + i]);
			iov[i].iov_len = BLCKSZ;
		}
        
		//4.3 哈希查找与 Chunk 分配
		tag.blockNum = blkno - chunk_offs; //对齐到chunk边界
		hash = get_hash_value(lfc_hash, &tag);
		cv = &lfc_ctl->cv[hash % N_COND_VARS]; //选择条件变量（64路hash 桶）

        //5. hash中查找当前块
		entry = hash_search_with_hash_value(lfc_hash, &tag, hash, HASH_ENTER, &found);
		if (found)
		{   
            //5.1 chunk已存在: Pin 住防止被 LRU 淘汰
			if (entry->access_count++ == 0)
			{
				lfc_ctl->pinned += 1;
				dlist_delete(&entry->list_node);
			}
		}
		else
		{	
            //5.2 chunk不存在，初始化entry （可能会触发LRU淘汰）
			if (!lfc_init_new_entry(entry, hash))
			{
				/* 由于缺少磁盘空间，则跳过
				 * We can't process this chunk due to lack of space in LFC,
				 * so skip to the next one
				 */
				blkno += blocks_in_chunk;
				buf_offset += blocks_in_chunk;
				nblocks -= blocks_in_chunk;
				continue;
			}
		}
		 //5.3 分配chunk号
		entry_offset = entry->offset;
		
        //6. 块状态机转换，并发控制机制
		for (int i = 0; i < blocks_in_chunk; i++)
		{
			FileCacheBlockState state = UNAVAILABLE;
			bool sleeping = false;
			while (lfc_ctl->generation == generation)
			{
				state = GET_STATE(entry, chunk_offs + i);
				if (state == PENDING) {
					SET_STATE(entry, chunk_offs + i, REQUESTED);
				} else if (state == UNAVAILABLE) {
					SET_STATE(entry, chunk_offs + i, PENDING);
					break;
				} else if (state == AVAILABLE) {
					break;
				}
				if (!sleeping)
				{
					ConditionVariablePrepareToSleep(cv);
					sleeping = true;
				}
				LWLockRelease(lfc_lock);
				ConditionVariableTimedSleep(cv, CV_WAIT_TIMEOUT, WAIT_EVENT_NEON_LFC_CV_WAIT);
				LWLockAcquire(lfc_lock, LW_EXCLUSIVE);
			}
			if (sleeping)
			{
				ConditionVariableCancelSleep();
			}
		}
        //7. 在io之前 释放锁
		LWLockRelease(lfc_lock);

		pgstat_report_wait_start(WAIT_EVENT_NEON_LFC_WRITE);
		INSTR_TIME_SET_CURRENT(io_start);
        
        //8.批量I/O写入
		rc = pwritev(lfc_desc, iov, blocks_in_chunk,
					 ((off_t) entry_offset * lfc_blocks_per_chunk + chunk_offs) * BLCKSZ);
		INSTR_TIME_SET_CURRENT(io_end);
		pgstat_report_wait_end();
	}
	LWLockRelease(lfc_lock);
}
```

**块状态机转换规则如下：**

| 当前状态    | Writer 动作          | 结果     | 说明               |
| ----------- | -------------------- | -------- | ------------------ |
| UNAVAILABLE | 设置 PENDING         | 继续写入 | 正常路径           |
| AVAILABLE   | 不修改               | 继续写入 | 覆盖旧数据         |
| PENDING     | 改为 REQUESTED，等待 | 阻塞     | 其他 Writer 正在写 |
| REQUESTED   | 继续等待             | 阻塞     | 已有等待者         |



**lfc_init_new_entry 详解（关键函数）**

```c++
static bool lfc_init_new_entry(FileCacheEntry* entry, uint32 hash)
{
    // 策略 1：如果未达上限
    if (lfc_ctl->used < lfc_ctl->limit)
    {
        // 子策略 1a：复用空洞
        if (!dlist_is_empty(&lfc_ctl->holes))
        {
            FileCacheEntry *hole = dlist_pop_head_node(&lfc_ctl->holes);
            entry->offset = hole->offset;  // 复用偏移量
            hash_search(..., HASH_REMOVE, ...);  // 删除空洞占位符
            lfc_ctl->used += 1;
        }
        // 子策略 1b：扩展文件
        else
        {
            entry->offset = lfc_ctl->size++;  // 分配新 offset
            lfc_ctl->used += 1;
        }
    }
    // 策略 2：已达上限，驱逐 LRU
    else if (!dlist_is_empty(&lfc_ctl->lru) && !lfc_do_prewarm)
    {
        FileCacheEntry *victim = dlist_pop_head_node(&lfc_ctl->lru);
        
        // 统计被驱逐的页面数
        for (int i = 0; i < lfc_blocks_per_chunk; i++)
        {
            if (GET_STATE(victim, i) == AVAILABLE)
            {
                lfc_ctl->used_pages -= 1;
                lfc_ctl->evicted_pages += 1;
            }
        }
        
        entry->offset = victim->offset;  // 复用 victim 的空间
        hash_search(..., HASH_REMOVE, ...);  // 删除 victim
    }
    // 策略 3：无法分配
    else
    {
        hash_search(..., HASH_REMOVE, ...);  // 删除刚创建的条目
        lfc_ctl->prewarm_canceled = true;    // 取消预热
        return false;
    }
    
    // 初始化新条目
    entry->access_count = 1;  // 已 Pin
    entry->hash = hash;
    lfc_ctl->pinned += 1;
    
    // 所有块初始化为 UNAVAILABLE
    for (int i = 0; i < lfc_blocks_per_chunk; i++)
        SET_STATE(entry, i, UNAVAILABLE);
    
    return true;
}
```



## 3.5 读取流程

`lfc_readv_select()`: 同步读取数据

**调用逻辑**

```c++
|-->neon_readv()
|	|-->lfc_readv_select() //本地 lfc，如有则返回
|	|-->communicator_request_pages() //远程pageserver请求
```



**主要逻辑**：原理跟写类似

```c++
1. 快速检查
   └─ if (lfc_maybe_disabled()) return -1;

2. 更新工作集统计（所有请求的页面）

3. 分 Chunk 迭代
   ├─ 构建 iovec 数组
   │  ├─ 跳过 mask 中已标记的页面
   │  └─ 对未标记的页面，指向 buffer
   │
   ├─ 获取锁
   │
   ├─ 在哈希表中查找 Chunk
   │  └─ 未找到？记录 miss，继续下一个 Chunk
   │
   ├─ Pin 住 Chunk
   │
   ├─ 逐块检查状态
   │  ├─ AVAILABLE：记录为 hit
   │  ├─ UNAVAILABLE：记录为 miss
   │  └─ PENDING/REQUESTED：等待条件变量
   │
   ├─ 释放锁
   │
   ├─ 如果有 hit，执行批量读取
   │  └─ preadv(fd, iov[], blocks, offset);
   │
   ├─ 重新获取锁
   │
   └─ 后处理
      ├─ 检查 generation
      ├─ 更新调用者的 mask（标记成功读取的页面）
      ├─ Unpin
      └─ 加入 LRU 尾部

4. 返回读取的页面数
```



## 3.6 预热

**主要流程**

- 关闭前保存 LFC 快照（get_local_cache_state）
- Compute Node 启动
- 加载快照，启动预热（lfc_prewarm）
- 后台并行加载页面
- 预热完成（90% 缓存恢复）
- 用户查询到达，大部分页面已在 LFC 中



```c++
|-->lfc_prewarm() //coordinator线程
|	|-->lfc_prewarm_main() //worker
|	|	|-->communicator_prefetch_register_bufferv() //发送请求到pageserver
|	|	|-->communicator_prefetch_receive() //接受预读的page
|	|	|	|-->lfc_prefetch() //写入lfc 文件中
```



 **操作命令**

1. `SELECT get_local_cache_state(10000);  -- 保存最多 10000 个 Chunk`

2. `SELECT prewarm_local_cache(snapshot, 4);  -- 使用 4 个 Worker`



**主要逻辑**

Coordinator线程：

1. **校验快照合法性**
2. **启动并管理多个后台 Worker**
3. **通过 DSM（动态共享内存）分发任务**
4. **等待所有 Worker 完成并收集结果**



Worker线程：

1. **附加到 DSM 共享内存** 
2. **根据 worker_id 划分任务**
3. **流水线预取页面（发送-接收并行）**
4. **调用 lfc_prefetch 写入 LFC**

```c++
void
lfc_prewarm_main(Datum main_arg)
{
	size_t snd_idx = 0, rcv_idx = 0;
	size_t n_sent = 0, n_received = 0;
	size_t fcs_chunk_size_log;
	size_t max_prefetch_pages;
	size_t prewarm_batch;
	size_t n_workers;
	dsm_segment *seg;
	FileCacheState* fcs;
	uint8* bitmap;
	BufferTag tag;
	PrewarmWorkerState* ws;
	uint32 worker_id = DatumGetInt32(main_arg);

	AmPrewarmWorker = true;

	pqsignal(SIGTERM, die);
	BackgroundWorkerUnblockSignals();
	
    //1. 附加 DSM 并读取快照
	seg = dsm_attach(lfc_ctl->prewarm_lfc_state_handle);

	fcs = (FileCacheState*) dsm_segment_address(seg);
	prewarm_batch = lfc_ctl->prewarm_batch;
	fcs_chunk_size_log = fcs->chunk_size_log;
	n_workers = lfc_ctl->n_prewarm_workers;
	max_prefetch_pages = lfc_ctl->n_prewarm_entries << fcs_chunk_size_log;
	ws = &lfc_ctl->prewarm_workers[worker_id];
	bitmap = FILE_CACHE_STATE_BITMAP(fcs);

	//2. 设置预热模式标志
	lfc_store_prefetch_result = true;
	lfc_do_prewarm = true; 

	elog(LOG, "LFC: worker %d start prewarming", worker_id);
    
    //3. 主循环：流水线预取算法（核心）
    //时间轴：维持 64 个并发请求（滑动窗口）
	//T0: ─→ send[1-64] ────────────────────────────→
	//T1:    ─→ send[65] ──→ recv[1] ──→
	//T2:       ─→ send[66] ──→ recv[2] ──→
	//T3:          ─→ send[67] ──→ recv[3] ──→
	//...
	//T66:                      ─→ send[130] ──→ recv[66] ──→
	while (!lfc_ctl->prewarm_canceled)
	{
        //3.1 发送阶段
		if (snd_idx < max_prefetch_pages)
		{
			if ((snd_idx >> fcs_chunk_size_log) % n_workers != worker_id)
			{
				/* If there are multiple workers, split chunks between them */
				snd_idx += 1 << fcs_chunk_size_log;
			}
			else
			{
				if (BITMAP_ISSET(bitmap, snd_idx))
				{
                    // 此页面在快照中标记为需要预热
					tag = fcs->chunks[snd_idx >> fcs_chunk_size_log];
					tag.blockNum += snd_idx & ((1 << fcs_chunk_size_log) - 1);
					
                    //构造 BufferTag
					if (!BufferTagIsValid(&tag)) {
						elog(ERROR, "LFC: Invalid buffer tag: %u", tag.blockNum);
					}

					if (!lfc_cache_contains(BufTagGetNRelFileInfo(tag), tag.forkNum, tag.blockNum))
					{
                        // 页面不在 LFC，发送预取请求
						(void)communicator_prefetch_register_bufferv(tag, NULL, 1, NULL);
						n_sent += 1;
					}
					else
					{
                        // 页面已在 LFC（可能在快照后被写入），跳过
						ws->skipped_pages += 1;
						BITMAP_CLR(bitmap, snd_idx);
					}
				}
				snd_idx += 1;
			}
		}
        
        //3.2 接受阶段
        //已发送的请求数 >= 已接收的请求数 + 批量大小； 或者 所有页面都已发送
		if (n_sent >= n_received + prewarm_batch || snd_idx == max_prefetch_pages)
		{
			if (n_received == n_sent && snd_idx == max_prefetch_pages)
			{
                // 所有页面都已处理完毕
				break;
			}
			if ((rcv_idx >> fcs_chunk_size_log) % n_workers != worker_id)
			{
				/* 此 Chunk 不属于当前 Worker */
				rcv_idx += 1 << fcs_chunk_size_log;
				continue;
			}

			/* 定位下一个需要接收的页面 */
			while (!BITMAP_ISSET(bitmap, rcv_idx))
			{
				rcv_idx += 1;
			}
			tag = fcs->chunks[rcv_idx >> fcs_chunk_size_log];
			tag.blockNum += rcv_idx & ((1 << fcs_chunk_size_log) - 1);
            
            // 从 Communicator 模块接收页面数据
    		// 调用 lfc_prefetch() 写入 LFC
			if (communicator_prefetch_receive(tag))
			{
				ws->prewarmed_pages += 1;
			}
			else
			{
				ws->skipped_pages += 1;
			}
			rcv_idx += 1;
			n_received += 1;
		}
	}
}
```



**运行例子**

```c++
时刻 T0（启动）：
  - Coordinator 创建 DSM（耗时 10ms）
  - 启动 4 个 Worker（耗时 50ms）

时刻 T1（Worker 开始）：
  - Worker #0 处理 Chunk #0, 4, 8, ... (2500 个)
  - Worker #1 处理 Chunk #1, 5, 9, ... (2500 个)
  - Worker #2 处理 Chunk #2, 6, 10, ... (2500 个)
  - Worker #3 处理 Chunk #3, 7, 11, ... (2500 个)

时刻 T2（预热中）：
  - 每个 Worker 维持 64 个并发请求
  - 平均每页耗时 5ms（网络延迟 + 处理）
  - 总耗时：2500 × 5ms / 64 ≈ 195 秒 ≈ 3.3 分钟

时刻 T3（完成）：
  - Worker 设置 completed 时间戳
  - Coordinator 收集统计
  - 清理 DSM
```

