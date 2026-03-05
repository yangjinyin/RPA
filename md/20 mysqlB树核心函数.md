# InnoDB B树模块函数功能文档 (btr0btr.cc)

**文件路径**: `storage/innobase/btr/btr0btr.cc`
**功能说明**: InnoDB B-tree (B树) 索引的核心实现模块，提供B树的创建、维护、修改和验证等功能。

---

## 目录
- [1. 错误报告与调试](#1-错误报告与调试)
- [2. B树根节点操作](#2-b树根节点操作)
- [3. B树页面管理](#3-b树页面管理)
- [4. B树创建与销毁](#4-b树创建与销毁)
- [5. 节点指针操作](#5-节点指针操作)
- [6. 页面分裂与合并](#6-页面分裂与合并)
- [7. 页面重组](#7-页面重组)
- [8. B树压缩](#8-b树压缩)
- [9. B树验证](#9-b树验证)
- [10. SDI索引操作](#10-sdi索引操作)

---

## 1. 错误报告与调试

### `btr_corruption_report()` (line 70)
**功能**: 报告索引页面损坏错误
**参数**:
- `block`: 损坏的块
- `index`: 索引树

**说明**: 输出索引页面标志不匹配的错误信息，包括页面ID、索引名和表名。

---

## 2. B树根节点操作

### `btr_root_block_get()` (line 152)
**功能**: 获取索引树的根节点并加S-latch或X-latch
**参数**:
- `index`: 索引树
- `mode`: RW_S_LATCH 或 RW_X_LATCH
- `mtr`: mini-transaction

**返回值**: 根页面block，已加锁
**说明**: 获取B树根页面用于读取或修改操作。

### `btr_root_get()` (line 182)
**功能**: 获取索引树的根节点并加SX-latch（用于segment访问）
**参数**:
- `index`: 索引树
- `mtr`: mini-transaction

**返回值**: 根页面指针
**说明**: SX锁不阻塞其他线程读取用户数据，但阻塞segment列表访问。

### `btr_height_get()` (line 195)
**功能**: 获取B树的高度（叶子节点为0层）
**参数**:
- `index`: 索引树
- `mtr`: mini-transaction

**返回值**: 树的高度
**说明**: 必须持有索引的S或X latch。

### `btr_root_adjust_on_import()` (line 247)
**功能**: 在导入表空间时检查和调整根节点
**参数**:
- `index`: 索引树

**返回值**: DB_SUCCESS 或错误码
**说明**: 验证根页面有效性，检查表格式标志匹配，调整file segment headers。

### `btr_root_fseg_adjust_on_import()` (line 223)
**功能**: 检查和更新根节点中的file segment header space id
**参数**:
- `seg_header`: segment header
- `page_zip`: 压缩页面
- `space`: 表空间ID
- `mtr`: mini-transaction

**返回值**: true表示有效

### `btr_root_fseg_validate()` (line 137)
**功能**: 检查根节点中的file segment header有效性（调试用）
**参数**:
- `seg_header`: segment header
- `space`: 表空间ID

**返回值**: true表示有效

---

## 3. B树页面管理

### `btr_page_create()` (line 319)
**功能**: 创建新的索引页面（非根节点）
**参数**:
- `block`: 要创建的页面block
- `page_zip`: 压缩页面
- `index`: 索引
- `level`: B树层级
- `mtr`: mini-transaction

**说明**:
- 根据索引类型设置页面类型（FIL_PAGE_RTREE/FIL_PAGE_SDI/FIL_PAGE_INDEX）
- 为空间索引初始化Split Sequence Number
- 设置索引ID

### `btr_page_alloc_priv()` (line 443)
**功能**: 为索引树分配新页面
**参数**:
- `index`: 索引
- `hint_page_no`: 提示页面号
- `file_direction`: 页面分裂方向（FSP_UP/FSP_DOWN）
- `level`: 树层级
- `mtr`: mini-transaction
- `init_mtr`: 初始化用的mini-transaction

**返回值**: 新分配的block，已加X-latch

### `btr_page_alloc_low()` (line 396)
**功能**: 分配新页面（内部实现）
**说明**: 根据层级决定从leaf segment还是top segment分配。

### `btr_page_alloc_for_ibuf()` (line 362)
**功能**: 为insert buffer树分配页面
**说明**: 从insert buffer的free list中获取页面。

### `btr_page_free()` (line 573)
**功能**: 释放索引树中的文件页面
**参数**:
- `index`: 索引树
- `block`: 要释放的block
- `mtr`: mini-transaction

**说明**: 不能用于释放field external storage pages。

### `btr_page_free_low()` (line 527)
**功能**: 释放页面（内部实现）
**说明**:
- 增加block的modify clock使其对optimistic search失效
- 区分ibuf索引、leaf页面、非leaf页面

### `btr_page_free_for_ibuf()` (line 509)
**功能**: 释放ibuf树的页面
**说明**: 将页面放回ibuf树的free list。

### `btr_page_empty()` (line 1412)
**功能**: 清空索引页面（保留全局数据如segment headers）
**参数**:
- `block`: 要清空的页面
- `page_zip`: 压缩页面
- `index`: 索引
- `level`: B树层级
- `mtr`: mini-transaction

---

## 4. B树创建与销毁

### `btr_create()` (line 831)
**功能**: 创建新的B树
**参数**:
- `type`: 索引类型（DICT_IBUF/DICT_CLUSTERED等）
- `space`: 表空间ID
- `index_id`: 索引ID
- `index`: 索引对象
- `mtr`: mini-transaction

**返回值**: 根页面号，FIL_NULL表示失败
**说明**:
- 创建segment headers
- 创建根页面
- 对ibuf索引特殊处理（单独的segment）

### `btr_free()` (line 1025)
**功能**: 释放临时表空间中的索引树
**参数**:
- `page_id`: 根页面ID
- `page_size`: 页面大小

### `btr_free_if_exists()` (line 1009)
**功能**: 如果持久索引树存在则释放
**参数**:
- `page_id`: 根页面ID
- `page_size`: 页面大小
- `index_id`: 索引ID
- `mtr`: mini-transaction

### `btr_free_but_not_root()` (line 957)
**功能**: 释放B树除根页面外的所有页面
**参数**:
- `block`: 根页面block
- `log_mode`: mtr日志模式

**说明**:
- 分步释放leaf segment
- 分步释放top segment（保留header）
- 必须在此之后调用btr_free_root()

### `btr_free_root()` (line 770)
**功能**: 释放B树根页面
**说明**: 必须先调用btr_free_but_not_root()。

### `btr_free_root_invalidate()` (line 794)
**功能**: 使索引根页面失效
**说明**: 设置INDEX_ID为BTR_FREED_INDEX_ID，使btr_free_root_check()找不到它。

### `btr_free_root_check()` (line 808)
**功能**: 准备释放B树，检查页面是否仍是匹配的B树页面
**返回值**: 根block，NULL表示不再是匹配的B树页面

### `btr_truncate()` (line 1046)
**功能**: 截断索引树（保留根页面）
**参数**:
- `index`: 聚簇索引

**说明**:
- 仅用于聚簇索引
- 释放除根页面外的所有页面
- 标记truncate操作（PAGE_MAX_TRX_ID设为IB_ID_MAX）

### `btr_truncate_recover()` (line 1102)
**功能**: truncate操作的恢复函数
**说明**: 检查是否有未完成的truncate操作，如有则重做。

### `btr_get_size()` (line 465)
**功能**: 获取B树的页面数量
**参数**:
- `index`: 索引
- `flag`: BTR_N_LEAF_PAGES 或 BTR_TOTAL_SIZE
- `mtr`: mini-transaction

**返回值**: 页面数量，ULINT_UNDEFINED表示索引不可用

---

## 5. 节点指针操作

### `btr_node_ptr_get_child()` (line 615)
**功能**: 根据节点指针记录获取子页面block
**参数**:
- `node_ptr`: 节点指针记录
- `index`: 索引
- `offsets`: 记录偏移量
- `mtr`: mini-transaction
- `type`: 锁类型

**返回值**: 子页面block

### `btr_node_ptr_set_child_page_no()` (line 586)
**功能**: 设置节点指针中的子页面号
**参数**:
- `rec`: 节点指针记录
- `page_zip`: 压缩页面
- `offsets`: 记录偏移量
- `page_no`: 子页面号
- `mtr`: mini-transaction

### `btr_node_ptr_delete()` (line 2781)
**功能**: 删除上层节点中指向某页面的节点指针
**参数**:
- `index`: 索引树
- `block`: 要删除节点指针的页面
- `mtr`: mini-transaction

---

## 6. 页面分裂与合并

### `btr_page_split_and_insert()` (line 2278)
**功能**: 分裂索引页面并插入tuple
**参数**:
- `flags`: undo logging和锁定标志
- `cursor`: 插入位置的cursor
- `offsets`: 输出，插入记录的偏移量
- `heap`: 内存堆
- `tuple`: 要插入的tuple
- `mtr`: mini-transaction

**返回值**: 插入的记录
**说明**:
- 持有索引树的X-latch
- 必须保证操作成功（提前预留足够磁盘空间）
- 尝试优化：插入到右兄弟页面
- 决定分裂点和方向
- 分配新页面
- 移动记录
- 插入tuple

### `btr_insert_into_right_sibling()` (line 2165)
**功能**: 如果cursor在页面末尾，尝试插入到右兄弟页面
**返回值**: 插入的记录，NULL表示未执行操作

### `btr_page_get_split_rec()` (line 1729)
**功能**: 计算分裂记录，确保tuple能放入半页
**返回值**: 分裂记录，NULL表示tuple将是半页的第一条记录

### `btr_page_get_split_rec_to_left()` (line 1638)
**功能**: 决定是否在左收敛点分裂（向左插入的收敛场景）
**返回值**: true表示建议分裂

### `btr_page_get_split_rec_to_right()` (line 1676)
**功能**: 决定是否在右收敛点分裂（向右插入的收敛场景）
**返回值**: true表示建议分裂

### `btr_page_insert_fits()` (line 1839)
**功能**: 判断插入操作在选定的分裂点下是否能放入半页
**返回值**: true表示可以放入

### `btr_page_tuple_smaller()` (line 2129)
**功能**: 判断tuple是否小于页面上的所有记录
**返回值**: true表示更小

### `btr_attach_half_pages()` (line 1987)
**功能**: 在索引树相应层级连接分裂后的两个半页
**参数**:
- `flags`: undo logging和锁定标志
- `index`: 索引树
- `block`: 被分裂的页面
- `split_rec`: 上半页的第一条记录
- `new_block`: 新的半页
- `direction`: FSP_UP 或 FSP_DOWN
- `mtr`: mini-transaction

**说明**:
- 更新父节点指针
- 更新同层页面的prev/next链接

### `btr_root_raise_and_insert()` (line 1455)
**功能**: 通过分裂根节点增加树高度并插入tuple
**参数**:
- `flags`: undo logging和锁定标志
- `cursor`: 插入位置（必须在根页面）
- `offsets`: 输出，插入记录的偏移量
- `heap`: 内存堆
- `tuple`: 要插入的tuple
- `mtr`: mini-transaction

**返回值**: 插入的记录
**说明**:
- 假设持有树的X-latch
- 操作必须成功，需提前保证足够磁盘空间
- 将根记录移到新页面
- 清空根页面
- 插入指向新页面的节点指针
- 分裂新页面并插入

### `btr_compress()` (line 2970)
**功能**: 尝试压缩索引页面（与兄弟页面合并）
**参数**:
- `cursor`: 页面上的cursor
- `adjust`: 是否调整cursor位置
- `mtr`: mini-transaction

**返回值**: true表示成功
**说明**:
- 检查左/右兄弟是否可以合并
- 移动记录到合并页面
- 删除节点指针
- 释放原页面
- 如果是唯一页面则提升到父层级

### `btr_lift_page_up()` (line 2803)
**功能**: 如果页面是层级上的唯一页面，将记录移到父页面，减少树高
**返回值**: 父block
**说明**: 页面不能为空。

### `btr_can_merge_with_page()` (line 4584)
**功能**: 检查cursor所在页面是否能与给定页面合并
**参数**:
- `cursor`: 要合并的页面上的cursor
- `page_no`: 兄弟页面号
- `merge_block`: 输出，合并block
- `mtr`: mini-transaction

**返回值**: true表示可以合并
**说明**: 必要时会重组merge_page。

### `btr_level_list_remove()` (line 2663)
**功能**: 从层级链表中移除页面
**参数**:
- `space`: 表空间
- `page_size`: 页面大小
- `page`: 要移除的页面
- `index`: 索引树
- `mtr`: mini-transaction

### `btr_discard_page()` (line 3505)
**功能**: 从B树丢弃页面（移除页面的最后一条记录时使用）
**参数**:
- `cursor`: 要丢弃页面上的cursor（不能是根页面）
- `mtr`: mini-transaction

**说明**:
- 不能用于根页面
- 整个页面同时移除
- 更新锁和链表

### `btr_discard_only_page_on_level()` (line 3432)
**功能**: 丢弃层级上的唯一页面，清空整个B树
**说明**:
- 理论上不应到达（btr_compress会调用btr_lift_page_up）
- 保存PAGE_MAX_TRX_ID
- 向上遍历到根节点

---

## 7. 页面重组

### `btr_page_reorganize()` (line 1369)
**功能**: 重组索引页面
**参数**:
- `cursor`: 页面cursor
- `index`: 索引树
- `mtr`: mini-transaction

**返回值**: true表示成功，false表示压缩页面重压缩失败
**说明**:
- 重新创建页面，复制记录
- 对压缩页面，如果重压缩失败则失败
- 成功后必须更新IBUF_BITMAP_FREE（压缩的leaf页面）

### `btr_page_reorganize_block()` (line 1338)
**功能**: 重组索引页面（block版本）
**参数**:
- `recovery`: 是否在恢复过程中（不更新锁和hash index）
- `z_level`: 压缩级别
- `block`: B树页面
- `index`: 索引树
- `mtr`: mini-transaction

### `btr_page_reorganize_low()` (line 1140)
**功能**: 重组页面的底层实现
**说明**:
- 复制页面到临时空间
- 重新创建页面
- 复制记录（不包括锁位）
- 复制max_trx_id（二级索引leaf页面）
- 压缩页面（如果适用）
- 更新锁位
- 记录redo日志

### `btr_parse_page_reorganize()` (line 1375)
**功能**: 解析页面重组的redo日志记录
**参数**:
- `ptr`: 缓冲区
- `end_ptr`: 缓冲区结束
- `index`: 记录描述符
- `compressed`: 是否压缩页面
- `block`: 要重组的页面
- `mtr`: mini-transaction

**返回值**: 日志记录结束位置

---

## 8. B树插入操作（非叶子层级）

### `btr_insert_on_non_leaf_level()` (line 1925)
**功能**: 在非叶子层级插入数据tuple
**参数**:
- `flags`: undo logging和锁定标志
- `index`: 索引
- `level`: 层级（必须>0）
- `tuple`: 要插入的记录
- `location`: 调用位置
- `mtr`: mini-transaction

**说明**:
- 假设持有树的X-latch
- 先尝试optimistic insert
- 失败则使用pessimistic insert

---

## 9. B树验证

### `btr_validate_index()` (line 4508)
**功能**: 检查索引树的一致性
**参数**:
- `index`: 索引
- `trx`: 事务
- `lockout`: 是否对索引加X-latch

**返回值**: true表示正常
**说明**:
- Full Text索引由辅助表实现，不检查
- 空间索引使用特殊验证
- 验证每个层级

### `btr_validate_level()` (line 4035)
**功能**: 验证索引树的某个层级
**参数**:
- `index`: 索引树
- `trx`: 事务
- `level`: 层级号
- `lockout`: 是否对索引加X-latch

**返回值**: true表示正常
**说明**:
- 检查页面是否在segment中
- 检查索引ID匹配
- 检查页面有效性
- 检查记录字段数量和长度
- 检查相邻页面记录顺序
- 检查父节点指针

### `btr_validate_spatial_index()` (line 4472)
**功能**: 对空间索引树执行验证
**返回值**: true表示无错误

### `btr_index_page_validate()` (line 3959)
**功能**: 检查索引页面记录的大小和字段数量
**参数**:
- `block`: 索引页面
- `index`: 索引

**返回值**: true表示正常

### `btr_index_rec_validate()` (line 3826)
**功能**: 检查记录的大小和字段数量
**参数**:
- `rec`: 索引记录
- `index`: 索引
- `dump_on_error`: 错误时是否打印十六进制dump

**返回值**: true表示正常
**说明**:
- 检查compact标志
- 检查字段数量
- 检查字段长度

### `btr_index_rec_validate_report()` (line 3811)
**功能**: 显示记录的识别信息（用于错误报告）

### `btr_validate_report1()` (line 4003)
**功能**: 报告索引树一个页面的错误

### `btr_validate_report2()` (line 4018)
**功能**: 报告索引树两个页面的错误

### `btr_check_node_ptr()` (line 3764)
**功能**: 检查节点指针（调试用）
**返回值**: true表示正常

---

## 10. 父节点查找

### `btr_page_get_father()` (line 747)
**功能**: 查找页面的上层节点指针
**参数**:
- `index`: B树索引
- `block`: 子页面
- `mtr`: mini-transaction
- `cursor`: 输出，节点指针记录上的cursor

**说明**: 假设持有树的X-latch。

### `btr_page_get_father_block()` (line 729)
**功能**: 返回页面的上层节点指针（带偏移量）
**返回值**: rec_get_offsets()的结果

### `btr_page_get_father_node_ptr()` (line 710)
**功能**: 返回页面的上层节点指针（内联包装函数）

### `btr_page_get_father_node_ptr_for_validate()` (line 717)
**功能**: 返回页面的上层节点指针（用于验证）

### `btr_page_get_father_node_ptr_func()` (line 637)
**功能**: 返回页面的上层节点指针（底层实现）
**参数**:
- `offsets`: 工作区
- `heap`: 内存堆
- `cursor`: 输入指向用户记录，输出指向节点指针
- `latch_mode`: BTR_CONT_MODIFY_TREE 或 BTR_CONT_SEARCH_TREE
- `location`: 调用位置
- `mtr`: mini-transaction

**返回值**: rec_get_offsets()的结果

---

## 11. 最小记录标记

### `btr_set_min_rec_mark()` (line 2757)
**功能**: 设置记录为预定义的最小记录
**参数**:
- `rec`: 记录
- `mtr`: mini-transaction

**说明**:
- 设置REC_INFO_MIN_REC_FLAG
- 区分compact和old格式
- 写redo日志

### `btr_set_min_rec_mark_log()` (line 2710, 2722)
**功能**: 写设置最小记录的redo日志记录
**参数**:
- `rec`: 记录
- `type`: MLOG_COMP_REC_MIN_MARK 或 MLOG_REC_MIN_MARK
- `mtr`: mini-transaction

### `btr_parse_set_min_rec_mark()` (line 2729)
**功能**: 解析设置最小记录的redo日志记录
**返回值**: 日志记录结束位置

---

## 12. 打印调试功能

### `btr_print_size()` (line 3645)
**功能**: 打印B树的大小信息
**参数**:
- `index`: 索引树

### `btr_print_recursive()` (line 3680)
**功能**: 递归打印索引树页面
**参数**:
- `index`: 索引树
- `block`: 索引页面
- `width`: 从开始和结束打印的条目数
- `heap`: rec_get_offsets()的内存堆
- `offsets`: rec_get_offsets()的缓冲区
- `mtr`: mini-transaction

### `btr_print_index()` (line 3732)
**功能**: 打印树中所有节点的目录和其他信息
**参数**:
- `index`: 索引
- `width`: 从开始和结束打印的条目数

---

## 13. SDI索引操作

### `btr_sdi_create_index()` (line 4684)
**功能**: 创建SDI索引并将根页面号存储在页面1和2中
**参数**:
- `space_id`: 表空间ID
- `dict_locked`: dict_sys mutex是否已获取

**返回值**: DB_SUCCESS 或 DB_ERROR
**说明**:
- SDI = Serialized Dictionary Information
- 创建SDI表和索引
- 写入根页面号到page 0
- 设置空间标志FSP_FLAGS_SET_SDI

### `btr_sdi_create()` (line 4668)
**功能**: 创建SDI索引（内部函数）
**参数**:
- `space_id`: 表空间ID
- `mtr`: mini-transaction
- `table`: SDI表

**返回值**: SDI索引的根页面号，FIL_NULL表示失败

---

## 核心设计概念

### Latching策略
InnoDB B树使用如下锁定策略：
1. **树锁（tree latch）**: 保护所有非叶节点
2. **节点锁（node latch）**: 每个节点有自己的锁
3. **搜索操作**:
   - 获取树的S-latch
   - 向下搜索，到达叶节点后释放树锁
   - 搜索时不获取非叶节点的latch，仅buffer-fix
4. **修改操作**:
   - 需要restructure时获取树的X-latch
   - 释放树锁后再移动记录

### 节点指针（Node Pointers）
- 非叶节点（n>0层）存储指向n-1层页面的节点指针
- 每个页面只有一个节点指针
- 节点指针包含：
  - 索引记录的前缀P（足够唯一确定记录）
  - 子页面的文件页面号（最后一个字段）
- 子页面可以存储 >= P且 < P1（下一个节点指针的前缀）的记录

### 最小记录（Minimum Record）
- 预定义的特殊记录，在任何字母顺序中最小
- 通过设置记录头的位标志表示
- 作为指向任意层级最左节点的节点指针前缀

### 文件页面分配（File Page Allocation）
- 根节点包含两个file segment headers
- **Leaf segment**: 分配叶页面，尽量保持磁盘连续
- **Top segment**: 分配非叶层级页面

---

## 函数调用关系示例

### 页面分裂流程
```c++
btr_page_split_and_insert()
  ├─> btr_insert_into_right_sibling()  // 尝试插入右兄弟
  ├─> btr_page_get_split_rec_to_right() // 决定分裂方向
  ├─> btr_page_get_split_rec_to_left()
  ├─> btr_page_get_split_rec()         // 计算分裂点
  ├─> btr_page_alloc()                 // 分配新页面
  ├─> btr_page_create()                // 创建新页面
  ├─> btr_attach_half_pages()          // 连接两个半页
  │     └─> btr_insert_on_non_leaf_level() // 插入父节点指针
  └─> page_cur_tuple_insert()          // 插入记录
```

### 页面合并流程
```c++
btr_compress()
  ├─> btr_can_merge_with_page()        // 检查是否可以合并
  │     └─> btr_page_reorganize_block() // 必要时重组
  ├─> page_copy_rec_list_start/end()   // 复制记录
  ├─> btr_level_list_remove()          // 从层级链表移除
  ├─> btr_node_ptr_delete()            // 删除父节点指针
  │     └─> btr_page_get_father()
  └─> btr_page_free()                  // 释放页面
  或
  └─> btr_lift_page_up()               // 如果是唯一页面，提升
```

### B树创建流程
```c++
btr_create()
  ├─> fseg_create()                    // 创建top segment
  ├─> fseg_create()                    // 创建leaf segment（非ibuf）
  ├─> page_create()                    // 创建根页面
  ├─> btr_page_set_index_id()
  └─> btr_page_set_next/prev()
```

---

## 注意事项

1. **事务性**: 所有B树修改操作都在mini-transaction（mtr）中进行
2. **并发控制**: 通过树锁和节点锁保护
3. **恢复**: 所有修改操作都写redo日志，支持崩溃恢复
4. **压缩页面**: 压缩页面有特殊处理逻辑
5. **空间索引**: R-tree索引有专门的处理路径
6. **Insert Buffer**: ibuf索引树有特殊的页面分配和释放机制
7. **锁**: 不同操作需要不同级别的锁（S/X/SX）

---

## 相关文件

- **btr0btr.h**: B树函数声明
- **btr0cur.cc**: B树cursor操作
- **btr0pcur.cc**: B树持久化cursor
- **btr0sea.cc**: B树自适应哈希索引
- **page0page.cc**: 页面操作
- **page0zip.cc**: 压缩页面操作

