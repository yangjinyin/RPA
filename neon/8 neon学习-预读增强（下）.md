# 1. 背景

在上一篇我们介绍了pg原生的预读，通过read_stream模块进行预读。

**Neon改进**:  通过解析父节点（Parent Node）的 Downlinks，打破了串行链条，实现了对未来叶子节点的批量预取。

核心改动思想：

- **提取 Downlinks**：父节点存储了指向所有子节点的指针。既然已经读了父节点，与其只拿一个子节点，不如把这一个页面里提到的所有子节点（`n_child` 个）全部异步拉取。
- **提前加载“路标”**：它不仅预取当前父节点下的子节点，还通过 `btpo_next`（或 `btpo_prev`）预取**下一个父节点**。



## 2. 具体实现

Neon预读支持三种场景

- 顺序扫描 （`enable_seqscan_prefetch`）
- 索引扫描 （`enable_indexscan_prefetch`）
- 全索引扫描 （`enable_indexonlyscan_prefetch`）



## 2.1 调用流程图

```c
扫描开始
   │
   ├─ 有查询条件 (_bt_first)
   │     ├─ _bt_search() → 找到起始页
   │       ├─ _bt_read_parent_for_prefetch(stack->bts_blkno)
   │           └─ 渐进式预取（distance=1开始）
   │
   └─ 无查询条件 (_bt_endpoint)
         ├─ _bt_get_endpoint() → 最左/右端点
         └─  _bt_read_parent_for_prefetch(parent)
               └─ 激进预取（distance=maximum）

扫描过程 (_bt_steppage)
   │
   └─ 当前父页子节点耗尽？
        └─ bt_read_parent_for_prefetch(next_parent)
                    └─ 切换到下一个父页
```

## 2.2 关键设计思想

### . **时机控制**

- 不在处理完所有子页后才预取下一个父页
- 在还剩`prefetch_maximum`个子页时开始预取
- 确保下一个父页在需要时已经在内存中

### . **内存预取数组**

- `prefetch_blocks[]`：存储待预取的块号
- 既包含子页，也包含下一个父页
- 索引扫描时会按顺序消费这个数组

### . **方向感知**

- 支持向前和向后扫描
- 维护`next_parent`指针（btpo_next或btpo_prev）



假设：`prefetch_maximum = 5`, 父页有 `8` 个子节点

预取队列： [子页1]   [子页2]  [子页3]  [下一个父页]  [子页4]...[子页8]   



## 2.3 实现细节

```c
static void
_bt_read_parent_for_prefetch(IndexScanDesc scan, BlockNumber parent, ScanDirection dir)
{
	Relation rel = scan->indexRelation;
	BTScanOpaque so = (BTScanOpaque) scan->opaque;
	Buffer		buf;
	Page		page;
	BTPageOpaque opaque;
	OffsetNumber offnum;
	OffsetNumber n_child;
	int			next_parent_prefetch_index;
	int			i, j;
	
    //1. 读取父页面
	buf = _bt_getbuf(rel, parent, BT_READ);
	page = BufferGetPage(buf);
	opaque = (BTPageOpaque) PageGetSpecialPointer(page);
    
    //2.  获取第一个数据键的偏移量
	offnum = P_FIRSTDATAKEY(opaque);
    
    //3. 计算子节点数量
	n_child = PageGetMaxOffsetNumber(page) - offnum + 1;

	//4. 计算父节点预读插入位置
    //核心思想：如果子节点数量大于最大预读距离，在倒数第 prefetch_maximum 个子节点位置插入父节点预读。
    //		  如果子节点数量 小于等于最大预读距离。则在第一个位置插入父节点预读。         
	next_parent_prefetch_index = (n_child > so->prefetch_maximum)
		? n_child - so->prefetch_maximum : 0;
	
    //5. 前向扫描的预读队列构建
	if (ScanDirectionIsForward(dir))
	{
		so->next_parent = opaque->btpo_next;
		if (so->next_parent == P_NONE)
			next_parent_prefetch_index = -1;

		for (i = 0, j = 0; i < n_child; i++)
		{
			ItemId itemid = PageGetItemId(page, offnum + i);
			IndexTuple itup = (IndexTuple) PageGetItem(page, itemid);
            
            //在计算的位置插入下一个父节点预读
			if (i == next_parent_prefetch_index)
				so->prefetch_blocks[j++] = so->next_parent; /* time to prefetch next parent page */
            
            // 提取子节点块号（downlink）
 			so->prefetch_blocks[j++] = BTreeTupleGetDownLink(itup);
		}
	}
	else //6. 后向扫描的预读队列构建
	{
		so->next_parent = opaque->btpo_prev;
		if (so->next_parent == P_NONE)
			next_parent_prefetch_index = -1;

		for (i = 0, j = 0; i < n_child; i++)
		{
			ItemId itemid = PageGetItemId(page, offnum + n_child - i - 1);
			IndexTuple itup = (IndexTuple) PageGetItem(page, itemid);
			if (i == next_parent_prefetch_index)
				so->prefetch_blocks[j++] = so->next_parent; /* time to prefetch next parent page */
			so->prefetch_blocks[j++] = BTreeTupleGetDownLink(itup);
		}
	}
	so->n_prefetch_blocks = j;
	so->last_prefetch_index = 0;
	_bt_relbuf(rel, buf);
}
```



# 3. 总结

这种大面积增加预取的操作，反映了从**“磁盘优先”**向**“网络优先”**设计的转变：

- **带宽换延迟**：虽然预取可能导致少量无效 I/O（如果扫描提前停止），但在云端，带宽相对富余，而延迟（Latency）是性能杀手。
- **计算与存储并行**：这让计算节点真正实现了“计算某页”与“拉取下十页”的并行化。

当然预取也不是万灵药：

- **Cache Pollution (缓存污染)**：如果预取太激进，会把 Cache 中原本有用的热数据挤出去。

- **CPU 与 I/O 的不平衡**：如果 I/O 子系统已经饱和，预取反而会增加 I/O 调度器的队列压力，导致正常的同步读请求延迟升高。