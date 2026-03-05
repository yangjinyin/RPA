# 1.介绍

PostgreSQL 的预取本质上是“**异步 I/O 建议**”。它的核心目标是：在 CPU 处理当前页面的同时，利用 I/O 子系统的并发能力，提前将后续页面从磁盘加载到操作系统页面缓存（OS Page Cache）中，从而隐藏 I/O 延迟。

pg的prefetch机制有两大场景：

- **WAL Recovery Prefetch(恢复预读)**：在故障恢复或备库回放 WAL 时，通过预读未来 WAL 记录引用的数据块来减少 I/O 等待。
- **Read Stream Prefetch(流式预读)**：在顺序扫描、索引扫描等查询操作中，通过 read_stream 机制实现自适应预读。



# 2.WAL Recovery Prefetch

## 2.1 调用堆栈

```c++
StartupXLOG()
|-->InitWalRecovery()
|	|-->XLogPrefetcherAllocate()           // 预读初始化
|-->PerformWalRecovery()
|	|-->ReadRecord()
|	|	|-->XLogPrefetcherReadRecord() //循环预读,实现核心函数，等会详细分析
|	|	|	|-->XLogPrefetcherNextBlock() //预读下一个block
|	|	|	|	|-->PrefetchSharedBuffer() //共享缓存区进行预读
|	|	|	|	|	|-->smgrprefetch() //SMGR接口
|	|	|	|	|	|	|-->mdprefetch() //文件系统接口
|	|	|	|	|	|	|	|-->FilePrefetch() //调用posix_fadvise()提示os读取file到os cache中
```

## 2.2 核心数据结构

```c
struct XLogPrefetcher {
    XLogReaderState *reader;           // WAL 读取器
    DecodedXLogRecord *record;         // 当前解码的 WAL 记录
    int next_block_id;                 // 下一个要处理的块 ID
    
    // 过滤机制：避免访问尚不存在的块
    HTAB *filter_table;                // 过滤表（哈希表）
    dlist_head filter_queue;           // 过滤队列
    
    // 去重机制：避免重复预读
    RelFileLocator recent_rlocator[4]; // 最近访问的 rlocator
    BlockNumber recent_block[4];       // 最近访问的块号
    int recent_idx;                    // 循环索引
    
    // I/O 深度管理
    LsnReadQueue *streaming_read;      // LSN 读取双向队列
    XLogRecPtr no_readahead_until;     // 禁用预读的 LSN 点
};
```

**LSN 读取队列**

```c
typedef struct LsnReadQueue {
    LsnReadQueueNextFun next;          // 获取下一个块的回调函数
    uint32 max_inflight;               // 最大并发 I/O 数
    uint32 inflight;                   // 当前进行中的 I/O
    uint32 completed;                  // 已完成但未消费的 I/O
    uint32 head;                       // 队列头（插入位置）
    uint32 tail;                       // 队列尾（消费位置）
    struct {
        bool io;                       // 是否需要等待 I/O
        XLogRecPtr lsn;                // 关联的 LSN
    } queue[FLEXIBLE_ARRAY_MEMBER];
} LsnReadQueue;
```

**统计信息结构，通过 `pg_stat_recovery_prefetch` 视图查看**

```c
typedef struct XLogPrefetchStats {
    pg_atomic_uint64 prefetch;         // 发起的预读次数
    pg_atomic_uint64 hit;              // 缓存命中次数
    pg_atomic_uint64 skip_init;        // 跳过的零初始化块
    pg_atomic_uint64 skip_new;         // 跳过的新/缺失块
    pg_atomic_uint64 skip_fpw;         // 跳过的全页镜像
    pg_atomic_uint64 skip_rep;         // 跳过的重复访问
    int wal_distance;                  // 预读距离（WAL 字节数）
    int block_distance;                // 块引用距离
    int io_depth;                      // I/O 深度
} XLogPrefetchStats;

```

## 2.3 核心逻辑

**1. XLogPrefetcherReadRecord()**：读取 WAL 记录时同时触发预读。

流程如下：

1. 检查是否需要重新配置（GUC 变化）
2. 释放上一条已回放的记录
3. 清理已完成的过滤器
4. 完成已回放 LSN 之前的 I/O
5. 触发预读逻辑（调用 lrq_prefetch）
6. 读取下一条 WAL 记录
7. 更新统计信息

```c
XLogRecord *
XLogPrefetcherReadRecord(XLogPrefetcher *prefetcher, char **errmsg)
{
	DecodedXLogRecord *record;
	XLogRecPtr	replayed_up_to;

	//1. 检测GUC参数变化（recovery_prefetch, maintenance_io_concurrency）
	if (unlikely(XLogPrefetchReconfigureCount != prefetcher->reconfigure_count))
	{
		uint32		max_distance;
		uint32		max_inflight;

		if (prefetcher->streaming_read)
			lrq_free(prefetcher->streaming_read);// 释放旧队列

		if (RecoveryPrefetchEnabled())
		{
			Assert(maintenance_io_concurrency > 0);
			max_inflight = maintenance_io_concurrency; // 最大并发I/O数
			max_distance = max_inflight * XLOGPREFETCHER_DISTANCE_MULTIPLIER;// 预读距离 = 4倍并发数
		}
		else
		{
			max_inflight = 1;
			max_distance = 1;
		}
		// 重新分配LSN读队列
		prefetcher->streaming_read = lrq_alloc(max_distance,
											   max_inflight,
											   (uintptr_t) prefetcher,
											   XLogPrefetcherNextBlock);

		prefetcher->reconfigure_count = XLogPrefetchReconfigureCount;
	}

	//2. 释放已重放记录. 返回改记录的LSN(replayed_up_to)
	replayed_up_to = XLogReleasePreviousRecord(prefetcher->reader);

	//3. 清理过滤器
	XLogPrefetcherCompleteFilters(prefetcher, replayed_up_to);

	//4. 将LSN < lsn的所有I/O标记为完成。腾出空间，来触发更多预读
	lrq_complete_lsn(prefetcher->streaming_read, replayed_up_to);

	//5. 解码队列为空（通常在第一次调用或长时间空闲后) 触发预读
	if (!XLogReaderHasQueuedRecordOrError(prefetcher->reader))
	{
		Assert(lrq_inflight(prefetcher->streaming_read) == 0);
		Assert(lrq_completed(prefetcher->streaming_read) == 0);
		lrq_prefetch(prefetcher->streaming_read);
	}

	//6.从解码队列头部弹出记录，若队列为空，则阻塞读取 
	record = XLogNextRecord(prefetcher->reader, errmsg);
	if (!record)
		return NULL;
    
	Assert(record == prefetcher->reader->record);

	if (record == prefetcher->record)
		prefetcher->record = NULL;

	//7.更新统计信息
	if (unlikely(record->lsn >= prefetcher->next_stats_shm_lsn))
		XLogPrefetcherComputeStats(prefetcher);

	Assert(record == prefetcher->reader->record);

	return &record->header;
}
```



**2. XLogPrefetcherNextBlock()** ：WAL预取器的**决策引擎核心**，作为 `LsnReadQueue` 的回调函数，决定下一个要预取的块。

**返回值**（三种状态）:

| 状态             | 含义                  | 后续动作              |
| ---------------- | --------------------- | --------------------- |
| `LRQ_NEXT_AGAIN` | WAL不足/需暂停        | 停止预取，等待更多WAL |
| `LRQ_NEXT_IO`    | 发起了真实I/O         | `inflight++`，记录LSN |
| `LRQ_NEXT_NO_IO` | 跳过预取（命中/过滤） | `completed++`，无I/O  |

```c
XLogRecord * XLogPrefetcherNextBlock 
{
	// 跳过全页镜像（有 FPW 就不需要读取）
	if (block->has_image) return LRQ_NEXT_NO_IO;

	// 跳过将被零初始化的块
	if (block->flags & BKPBLOCK_WILL_INIT) return LRQ_NEXT_NO_IO;

	// 跳过被过滤的块（尚不存在）
	if (XLogPrefetcherIsFiltered(...)) return LRQ_NEXT_NO_IO;

	// 跳过最近 4 个块内的重复访问
	for (int i = 0; i < 4; ++i) 
    	if (块号相同 && rlocator 相同) return LRQ_NEXT_NO_IO;

	// 检查文件和块是否存在
	if (!smgrexists() || block->blkno >= smgrnblocks()) 
    	return LRQ_NEXT_NO_IO;

	// 真正执行预读
	result = PrefetchSharedBuffer(reln, forknum, blockno);
}
```



**3. PrefetchSharedBuffer()**：对共享缓冲区执行预读

```c
PrefetchBufferResult PrefetchSharedBuffer(SMgrRelation smgr_reln,
                                          ForkNumber forkNum,
                                          BlockNumber blockNum) {
    // 1. 查找缓冲区映射表
    buf_id = BufTableLookup(&newTag, newHash);
    
    // 2. 如果在缓冲区中，返回命中
    if (buf_id >= 0) return {buffer, false};
    
    // 3. 如果不在，调用操作系统预读接口
    #ifdef USE_PREFETCH
    if (smgrprefetch(smgr_reln, forkNum, blockNum, 1))
        result.initiated_io = true;
    #endif
}

```



**4. smgrprefetch() → mdprefetch()**：底层文件系统预读

```c
bool mdprefetch(SMgrRelation reln, ForkNumber forknum, 
                BlockNumber blocknum, int nblocks) {
    #ifdef USE_PREFETCH
    // 定位文件段和偏移量
    v = _mdfd_getseg(reln, forknum, blocknum, ...);
    seekpos = (off_t) BLCKSZ * (blocknum % RELSEG_SIZE);
    
    // 调用 posix_fadvise(POSIX_FADV_WILLNEED)
    FilePrefetch(v->mdfd_vfd, seekpos, BLCKSZ * nblocks, ...);
    #endif
}

```



# 3.Read Stream Prefetch

在 PostgreSQL 17 版本中引入的 `read_stream` 模块，是近年来pg数据库io架构最重大的重构之一。

在 `read_stream` 出现之前，预取（Prefetch）是“硬编码”的。比如在 `BitmapScan` 中，代码手动计算要预取多少块并调用 `PrefetchBuffer`。

**`read_stream` 设计思想：** 调用者只需要告诉我接下来可能需要哪些块的逻辑（通过回调函数），ReadStream 模块来负责控制什么时候**、**以多大的并发度发给底层存储。

## 3.1主要架构图

```c
┌─────────────────────────────────────────────────────────────┐
│                    Upper Layer (Heap Scan)                  │
│  - heap_beginscan()                                          │
│  - heapgettup()                                              │
│  - heap_fetch_next_buffer()                                  │
└────────────────┬────────────────────────────────────────────┘
                 │
                 │ Callback: heap_scan_stream_read_next_parallel()
                 ↓
┌─────────────────────────────────────────────────────────────┐
│              Read Stream Layer (read_stream.c)               │
│  - read_stream_next_buffer()                                 │
│  - read_stream_look_ahead()                                  │
│  - read_stream_start_pending_read()                          │
└────────────────┬────────────────────────────────────────────┘
                 │
                 │ StartReadBuffers() / WaitReadBuffers()
                 ↓
┌─────────────────────────────────────────────────────────────┐
│           Buffer Manager Layer (bufmgr.c)                    │
│  - StartReadBuffersImpl()                                    │
│  - PinBufferForBlock()                                       │
│  - PrefetchSharedBuffer() [if not in buffer pool]            │
└────────────────┬────────────────────────────────────────────┘
                 │
                 │ smgrprefetch()
                 ↓
┌─────────────────────────────────────────────────────────────┐
│              Storage Manager (md.c)                          │
│  - mdprefetch()                                              │
│  - FilePrefetch() → posix_fadvise(POSIX_FADV_WILLNEED)     │
└─────────────────────────────────────────────────────────────┘

```

## 3.2 核心逻辑

**核心数据结构**

```c
struct ReadStream {
    int16 max_ios;                     // 最大并发 I/O
    int16 io_combine_limit;            // I/O 合并上限
    int16 ios_in_progress;             // 进行中的 I/O 数
    int16 queue_size;                  // 队列大小
    int16 max_pinned_buffers;          // 最大固定缓冲区数
    int16 pinned_buffers;              // 当前固定缓冲区数
    int16 distance;                    // 预读距离（自适应）
    bool advice_enabled;               // 是否启用预读建议
    
    // 回调机制
    ReadStreamBlockNumberCB callback;  // 获取下一个块号的回调
    void *callback_private_data;
    
    // 流控
    BlockNumber seq_blocknum;          // 下一个期望的顺序块号
    BlockNumber pending_read_blocknum; // 待读取块号
    int16 pending_read_nblocks;        // 待读取块数
    
    // 循环队列
    InProgressIO *ios;                 // I/O 数组
    int16 oldest_buffer_index;         // 最老缓冲区索引
    int16 next_buffer_index;           // 下一个缓冲区索引
    Buffer buffers[FLEXIBLE_ARRAY_MEMBER];
};
```



**`read_stream_begin_relation()`**： 初始化流。你需要传入 `Relation`、并发度限制以及最重要的回调函数。这个回调函数告诉stream模块下一批次要读哪些块。

```c
ReadStream *read_stream_begin_relation(int flags, ...)
{
    // 1. 计算最大并发 I/O 数
    if (flags & READ_STREAM_MAINTENANCE)
        max_ios = get_tablespace_maintenance_io_concurrency(tablespace_id);
    else
        max_ios = get_tablespace_io_concurrency(tablespace_id);
    
    // 2. 计算最大固定缓冲区数
    max_pinned_buffers = Max(max_ios * 4, io_combine_limit);
    max_pinned_buffers = Min(max_pinned_buffers, 
                             GetAccessStrategyPinLimit(strategy));
    
    // 3. 限制当前进程的总固定缓冲区数
    if (SmgrIsTemp(smgr))
        LimitAdditionalLocalPins(&max_pinned_buffers);
    else
        LimitAdditionalPins(&max_pinned_buffers);
    
    // 4. 分配队列空间（需要额外的溢出空间）
    queue_size = max_pinned_buffers + 1;  // +1 用于区分满/空状态
    queue_overflow = io_combine_limit - 1; // 合并 I/O 时的临时溢出
    
    // 5. 初始化自适应距离
    if (flags & READ_STREAM_FULL)
        stream->distance = Min(max_pinned_buffers, io_combine_limit);
    else
        stream->distance = 1;  // 从 1 开始，假设全缓存
    
    // 6. 配置预读建议
    #ifdef USE_PREFETCH
    if ((io_direct_flags & IO_DIRECT_DATA) == 0 &&
        (flags & READ_STREAM_SEQUENTIAL) == 0 &&
        max_ios > 0)
        stream->advice_enabled = true;
    #endif
    
    return stream;
}

```



**`read_stream_next_buffer()`**： 这是主循环调用的函数。

**步骤 1: 等待 I/O 完成**

```c
if (stream->ios_in_progress > 0 &&
    stream->ios[stream->oldest_io_index].buffer_index == oldest_buffer_index)
{
    WaitReadBuffers(&stream->ios[io_index].op);
    stream->ios_in_progress--;
    
    // 根据 I/O 类型调整距离
    if (op->flags & READ_BUFFERS_ISSUE_ADVICE)
    {
        // 随机访问：快速增长
        stream->distance = Min(stream->distance * 2, max_pinned_buffers);
    }
    else
    {
        // 顺序访问：缓慢增长至 io_combine_limit
        stream->distance = Min(stream->distance * 2, io_combine_limit);
    }
}
```

**步骤 2:如果队列里已经有预取好的 Buffer，取出最老的缓冲区**

```c
buffer = stream->buffers[oldest_buffer_index];

// 前进 oldest_buffer_index（循环队列）
stream->pinned_buffers--;
stream->oldest_buffer_index++;
if (stream->oldest_buffer_index == stream->queue_size)
    stream->oldest_buffer_index = 0;
```

**步骤 3: 触发预读**

```c
read_stream_look_ahead(stream, false);
```



## 3.3 预读

**read_stream_look_ahead() **：在不超过距离限制和 I/O 并发限制的前提下，尽可能启动更多 I/O

```c
static void read_stream_look_ahead(ReadStream *stream, bool suppress_advice)
{
    while (stream->ios_in_progress < stream->max_ios &&
           stream->pinned_buffers + stream->pending_read_nblocks < stream->distance)
    {
        BlockNumber blocknum;
        
        // 1. 检查是否需要启动待处理的读取
        if (stream->pending_read_nblocks == stream->io_combine_limit)
        {
            read_stream_start_pending_read(stream, suppress_advice);
            suppress_advice = false;
            continue;
        }
        
        // 2. 调用回调函数获取下一个块号
        blocknum = read_stream_get_block(stream, per_buffer_data);
        if (blocknum == InvalidBlockNumber)
        {
            stream->distance = 0;  // 流结束
            break;
        }
        
        // 3. 尝试合并到待处理的读取
        // 如果回调函数返回的下一个块号恰好和当前待读取批次的最后一个块是物理连续的，
        // 那么就不发请求，而是简单地把计数器加 1
        if (stream->pending_read_nblocks > 0 &&
            stream->pending_read_blocknum + stream->pending_read_nblocks == blocknum)
        {
            stream->pending_read_nblocks++;
            continue;
        }
        
        // 4. 无法合并，启动待处理的读取
        //如果新拿到的块是不连续的，那么必须先完成之前的“连续批次”发送，才能开始处理这个新的、不连续的块
        while (stream->pending_read_nblocks > 0)
        {
            read_stream_start_pending_read(stream, suppress_advice);
            if (stream->ios_in_progress == stream->max_ios)
            {
                // I/O达到上限，则 unget 掉当前块并退出
                read_stream_unget_block(stream, blocknum);
                return;
            }
        }
        
        // 5. 开始新的待处理读取
        stream->pending_read_blocknum = blocknum;
        stream->pending_read_nblocks = 1;
    }
    
    // 6.最后发送一些零散请求。
    // 只要满足以下任一情况，就会立即触发读取
    // - a. 达到了合并限制
    // - b. 达到了预取距离上限，且当前没有任何 Pin 住的 Buffer（说明需要尽快填充流水线）
    // - c. 到达了流的末尾
    if (stream->pending_read_nblocks > 0 &&
        (stream->pending_read_nblocks == stream->io_combine_limit ||
         (stream->pending_read_nblocks == stream->distance &&
          stream->pinned_buffers == 0) ||
         stream->distance == 0))
    {
        // 立刻启动vectored i/o 读取
        read_stream_start_pending_read(stream, suppress_advice);
    }
}

```

**I/O 合并示例**:

回调函数返回序列: 10, 11, 12, 50, 51, 100

处理过程:
1. blocknum=10 → pending_read=[10, 1]
2. blocknum=11 → pending_read=[10, 2]  (合并)
3. blocknum=12 → pending_read=[10, 3]  (合并)
4. blocknum=50 → 启动 [10-12], pending_read=[50, 1]
5. blocknum=51 → pending_read=[50, 2]  (合并)
6. blocknum=100 → 启动 [50-51], pending_read=[100, 1]

结果: 3 个读取请求覆盖 6 个块



## 3.4 启动I/O

`read_stream_start_pending_read()`

实现了一套自适应距离控制算法。

## 3.5 三种行为模式

**行为 A：全缓存模式**

**特征**: 所有块已在缓冲池中, 调整逻辑:

```c
if (!need_wait) {
    if (stream->distance > 1)
        stream->distance--;  // 衰减
}
```

**原因**: 预读无效，应最小化开销

------

**行为 B：顺序 I/O 模式**

**特征**: 需要 I/O 但访问顺序，或禁用了预读建议 **距离策略**: `distance ≤ io_combine_limit` **调整逻辑**:

```c
if (need_wait && !(flags & READ_BUFFERS_ISSUE_ADVICE)) {
    if (stream->distance > stream->io_combine_limit)
        stream->distance--;
    else {
        distance = stream->distance * 2;
        distance = Min(distance, stream->io_combine_limit);
        stream->distance = distance;
    }
}
```

**原因**: 顺序访问由内核自动检测，只需合并 I/O

------

**行为 C：随机 I/O 模式**

**特征**: 需要 I/O 且访问随机，发出了预读建议 **距离策略**: `distance ≤ max_pinned_buffers` **调整逻辑**:

```c
if (need_wait && (flags & READ_BUFFERS_ISSUE_ADVICE)) {
    distance = stream->distance * 2;
    distance = Min(distance, stream->max_pinned_buffers);
    stream->distance = distance;
}
```

**原因**: 随机访问需要高 I/O 并发度以隐藏延迟



## 3.6 总结

read_stream模块它是 PG 迈向真正的内核级异步 I/O 的关键一步。传统的 `read()` 是阻塞的，但 `read_stream` 的结构天然适配 `io_uring` 这种提交请求和获取结果分离的模式。它允许底层将连续的块合并为一个 `readv()` 系统调用，显著减少系统调用次数。