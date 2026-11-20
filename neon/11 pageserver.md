Pageserver 它主要做四件事：

1. 接收并处理 WAL
2. 按 LSN 保存页面历史
3. 根据页面 key 和目标 LSN 重建页面
4. 根据key+lsn 为 compute提供页面



### 数据层次

```c++
TenantManager
  └── TenantShard
        └── Timeline
              ├── LayerMap
              ├── WAL receiver
              ├── compaction
              ├── GC
              └── remote storage
```

`TenantManager`：  可以理解为租户。

`TenantShard` ：某个租户分片。

`Timeline` ：负责一条数据库branch。



### 启动流程

**pageserver/src/bin/pageserver.rs**

```c++
  main()
    ↓
解析命令行参数  //let arg_matches = cli().get_matches();负责解析--config --version  ---workdir
    ↓
读取 pageserver.toml // initialize_config()
    ↓
初始化日志、metrics、IO engine //logging::init()  set_build_info_metric()
    ↓
创建 TenantManager //tenant_manager = mgr::init()
    ↓
加载 Tenant 和 Timeline //TenantManager::load_tenant() && load_timelines_metadata()
    ↓
启动 HTTP/HTTPS 服务 //Server::new(service, http_listener, None)
    ↓
启动 Page Service  //page_service::spawn()
    ↓
启动 gRPC 服务 //GrpcPageServiceHandler::spawn()

```

Pageserver 启动完成之后，真正开始接收 Safekeeper WAL 



### 接收WAL

Timeline 激活时通过 `Timeline::launch_wal_receiver`动 `WalReceiver`

```c++
WalReceiver::start()
|-->connection_manager_loop_step()
|	|-->handle_walreceiver_connection()
|	|	|-->1. 建立 START_REPLICATION
|	|	|-->2. 创建 WalIngest
|	|	|-->3. 接收WAL batch
|	|	|-->4. WalIngest::ingest_record()
```

单条 WAL 记录的核心入口是 `WalIngest::ingest_record`。它会：

- 处理元数据 WAL
- 更新 checkpoint
- 把 WAL record 变成页面变更  layer层 写入 `DatadirModification`
- 更新 Timeline 的 LSN
- 解析reocrd，处理事务提交相关记录（主要作用是维护clog事务状态信息，后续用来判断可见性）
- 处理 relation、CLOG、relmap、SLRU 等全局对象



### Layer层

Pageserver 的 ingest 阶段主要负责把 WAL 变成页面历史数据layer，真正的 PostgreSQL WAL redo通常延迟到页面被读取时执行。

这样的好处：

1.  读取与回放解耦

1.  layer层天然支持任意lsn的历史查询

1.  layer层可以在随时随地的创建分支

1.  layer层是顺序io，可以批量写入和读取

1.  layer层可以上传到对象存储中，本地无需保存

    
    
    
    

### GetPage

Page Service 面向 Compute 提供页面读取服务，可以提供多种形式

GetPage@LSN
GetPageBatch
GetRelationSize
GetDbSize
GetSlruSegment

```c++
Compute
|-->GetPage(rel, fork, block, lsn)
|	|-->1. page_service   //解析 Compute 的页面请求
|	|-->2. TenantManager  //找到 TenantShard
|	|-->3. TenantShard   //找到 TenantShard
|	|-->4. Timeline     //找到对应的branch分支层
|	|-->5. LayerMap    //找到对应的layer层的wal日志流
|	|-->5. 读取 page image / WAL records //根据 key 和 LSN 读取页面
|	|-->6. walredo  //必要时执行 WAL redo
|	|-->7. 返回页面
```

这里redo实现的机制：Pageserver 会启动特殊模式的 PostgreSQL 进程，这使得 Pageserver 可以复用 PostgreSQL 官方 WAL redo 代码







### 备库cache回放

页面是否需要重放，主要看 WAL record 的 LSN 和页面已有的 `PageLSN`比较

```c++
WAL record
|	|-->ApplyWalRecord()
|	|	|-->heap_redo / btree_redo / ...
|	|	|	|-->XLogReadBufferForRedo
|	|	|	|	|-->1. 找到 shared_buffers 中已有 buffer
|	|	|	|	|-->2. 加锁
|	|	|	|	|-->3. 根据页面 LSN 判断是否需要 redo
|	|	|	|	|-->4. 原地修改 buffer
|	|	|	|	|-->5. 更新页面 LSN
|	|	|	|	|-->6. MarkBufferDirty
|	|	|	|	|-->7. 异步刷到本地cache中
```





### LFC 回放

```C++
LFC 中的旧页面
|	|-->读入 shared_buffers
|	|	|-->PostgreSQL redo 原地修改 shared_buffers
|	|	|-->页面写回时覆盖更新 LFC

```

这种方式污染了shared_buffers，后续其实可以优化下。



### Vacuum

需要开启 **hot_standby_feedback**，Neon备库没有直接连接主库，xmin反馈需要经过safekeeper转发；步骤如下：

1. 备库把xmin 发给safekeeper （`send_wal.rs:1006`）。safekeeper汇总所有备库，取最小的xmin(`send_wal.rs:357`)。

2. 主库上的 walproposer 从各 safekeeper 的响应中再取一次最小值。（`CombineHotStanbyFeedbacks()`）
3. walproposer 调用 `ProcessStandbyHSFeedback()`。这一步之后，主库 VACUUM 就不会清理比这个 xmin 新的死元组。