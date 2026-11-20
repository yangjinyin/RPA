## 版本速览

表格

| 版本 | 发布日期   | 核心主题                                               |
| ---- | ---------- | ------------------------------------------------------ |
| 13   | 2020-09-24 | B-tree 去重、增量排序、并行 vacuum                     |
| 14   | 2021-09-30 | 连接池高并发、JSONB 下标、multirange、VACUUM failsafe  |
| 15   | 2022-10-13 | MERGE、逻辑复制行 / 列过滤、zstd、统计系统迁入共享内存 |
| 16   | 2023-09-14 | 并行查询扩面、备库逻辑发布、pg_stat_io、SIMD           |
| 17   | 2024-09-26 | VACUUM 内存重构、WAL / 流式 I/O、增量备份、JSON_TABLE  |
| 18   | 2025-09-25 | 异步 I/O、B-tree skip scan、虚拟生成列、uuidv7、OAuth  |

------

## PostgreSQL 13（2020）

**性能与索引**

- **B-tree 索引条目去重（deduplication）**：重复键只存一次，低基数列索引显著缩小，升级后需 `REINDEX` 才能生效。
- **增量排序（incremental sort）**：中间结果已按排序键前导列有序时，只对剩余键排序；`enable_incremental_sort` 控制。
- **索引并行 vacuum**；`vacuumdb --parallel`、`reindexdb --jobs` 并行化。
- **哈希聚合可溢出到磁盘**（配合 `hash_mem_multiplier`），不再因预估超 `work_mem` 而放弃 HashAggregate。
- **分区表 / 聚合查询性能提升**；partitionwise join支持分区边界不完全一致的场景。
- 插入（insert-only）负载也能触发 autovacuum（此前只触发 auto-analyze）。

**SQL / 类型 / 函数**

- 内置 `gen_random_uuid()`（v4 UUID），不再依赖 uuid-ossp/pgcrypto。
- 新增 64 位事务 ID 类型 `xid8`；`regcollation`；多态类型 `anycompatible` 系列。
- `jsonb_set_lax()`、jsonpath `.datetime()`、SQL 标准 `NORMALIZE()` / `IS NORMALIZED`。
- 扩展统计可单独设置 statistics target（`ALTER STATISTICS ... SET STATISTICS`）。
- 分区表支持行级 `BEFORE` 触发器。

**复制 / 安全 / 运维**

- 分区表可整体加入逻辑复制 publication（`publish_via_partition_root`）。
- 默认最低 TLS 版本提至 1.2；libpq 支持 channel binding 防中间人攻击。
- **可信扩展（trusted extensions）**：非超级用户可安装标记为 trusted 的扩展。
- `pg_stat_statements` 可跟踪 planning time；psql 默认提示符显示事务状态（`%x`）。

------

## PostgreSQL 14（2021）

**性能与索引**

- 嵌套循环连接内层结果缓存（**Memoize**，`enable_memoize`）。
- 并行顺序扫描 I/O 改进：按块组分配给并行 worker（`maintenance_io_concurrency`）。
- **B-tree 索引在更新时主动删除过期条目**，减少页分裂和索引膨胀。
- **VACUUM failsafe**：接近事务 ID 回卷时跳过非必要清理、强制加速；`INDEX_CLEANUP auto` 可跳过无意义索引清理；`PROCESS_TOAST` 可跳过 TOAST 表。
- BRIN 索引支持每个范围记录多个 min/max、支持 **Bloom filter**。
- 高 CPU / 高会话数下 MVCC 可见性快照性能大幅改善（大量空闲连接场景受益）。
- 正则、Unicode normalize 性能大幅提升。

**SQL / 类型 / 函数**

- **JSONB 与 hstore 支持下标语法**（`data['key']`），下标框架通用化。
- **multirange 多范围类型**（每个 range 类型自动生成对应 multirange）。
- CTE 递归查询支持 SQL 标准 `SEARCH` / `CYCLE` 子句。
- SQL 存储过程可通过 `OUT` 参数返回数据；SQL 函数支持标准函数体语法。
- TOAST 支持 **LZ4 压缩**（列级或 `default_toast_compression`）；numeric 支持 `Infinity`。
- 扩展统计可建在表达式上（`pg_stats_ext_exprs`）。

**连接 / 监控 / 安全**

- **libpq pipeline**：高延迟链路可流水线发送多个查询。
- 预定义角色 `pg_read_all_data`、`pg_write_all_data`、`pg_database_owner`。
- 新视图：`pg_stat_wal`、`pg_stat_progress_copy`、`pg_stat_replication_slots`、`pg_backend_memory_contexts`。
- SSL 支持 SNI；客户端证书可按 DN（不只 CN）匹配。

------

## PostgreSQL 15（2022）

**SQL / 开发**

- **SQL `MERGE` 命令**：一条语句内完成条件 insert/update/delete。
- **`UNIQUE NULLS NOT DISTINCT`**：唯一约束 / 索引可把多个 NULL 视为相同。
- 正则兼容函数：`regexp_count()`、`regexp_instr()`、`regexp_like()`、`regexp_substr()`。
- 逻辑解码 / 复制可按 xid 过滤；`^@` 前缀算子在 C collation 下可用 B-tree。

**性能**

- 内存排序与磁盘排序算法重写，超 `work_mem` 排序更快更省内存。
- `SELECT DISTINCT` 可并行；`NOT IN` 大常量列表改用 hash 查找；窗口函数 row_number/rank 等提速。
- WAL full-page writes 支持 **LZ4 / zstd** 压缩；UTF-8 校验一次处理 16 字节。

**逻辑复制 / 恢复**

- **publication 支持列清单与行过滤（WHERE）**，可选择性复制表内容。
- 订阅端 `disable_on_error`；新增 `pg_stat_subscription_stats`。
- 崩溃恢复期间运行 checkpointer/bgwriter；**WAL 恢复预取**（`recovery_prefetch`）加速长恢复。
- 归档支持可加载模块（`archive_library`），不必再写 shell 脚本。

**压缩 / 备份 / 运维**

- 支持 **zstd**；`pg_basebackup` 服务端压缩（lz4/zstd）。
- 累积统计系统迁入**共享内存**，取消独立 stats collector 进程（UDP 架构移除）。
- 日志支持 JSON 结构化输出（`log_destination=jsonlog`）；默认记录 checkpoint 和慢 autovacuum。
- 新增 `pg_walinspect` 扩展（SQL 级 WAL 检查）；pg_upgrade 保留表空间 / 库 OID 和 relfilenode。
- **安全收紧**：`public` schema 默认不再对所有角色开放 `CREATE`（归 `pg_database_owner` 所有）。

------

## PostgreSQL 16（2023）

**查询性能**

- 规划器可并行执行 **FULL / RIGHT 连接**；优化 RIGHT/OUTER anti-join。
- 带 `DISTINCT`/`ORDER BY` 的聚合、窗口函数执行更优；增量排序用于 `SELECT DISTINCT`。
- `COPY` 单线程 / 并发批量加载最高提速 **300%**。
- **SIMD CPU 加速**（x86/ARM）：ASCII/JSON 字符串处理、数组与子事务搜索。
- libpq 客户端支持**多主机负载均衡**。

**逻辑复制（重点版本）**

- **备节点（standby）可作为逻辑复制发布源**，把变更再级联到下游。
- 订阅端**并行应用大型事务**；无主键表用 B-tree 索引而非顺序扫描定位行；初始同步可用二进制格式。
- 支持**双向逻辑复制**（两个发布者之间互相同步）。
- 新预定义角色 `pg_create_subscription`。

**SQL / 开发**

- SQL/JSON 扩充：`JSON_ARRAY()`、`JSON_ARRAYAGG()`、`IS JSON` 等。
- 数值字面量支持下划线分隔（`5_432_000`）和非十进制（`0x`/`0o`/`0b`）。
- psql 新增 `\bind` 参数化查询。
- ICU 构建默认启用并可自定义 ICU 排序规则。

**监控 / 安全**

- 新视图 **`pg_stat_io`**：I/O 访问模式细粒度分析。
- `pg_stat_all_tables` 增加最后扫描时间戳。
- `pg_hba.conf` 支持正则匹配用户名 / 库名和 `include` 指令；客户端 `require_auth`、`sslrootcert="system"`；Kerberos 信任委托。

------

## PostgreSQL 17（2024）

**系统级性能**

- **VACUUM 内存管理重构**，内存消耗最高降低 **20 倍**，速度更快。
- WAL 处理改进，高并发写入吞吐最高 **2 倍**。
- 新的**流式 I/O 接口**加速顺序扫描和 `ANALYZE`。
- B-tree `IN` 子句查询优化；**BRIN 支持并行构建**；`NOT NULL` 约束与 CTE 规划改进。
- 更多 SIMD（含 **AVX-512** 加速 `bit_count`）。

**SQL / JSON / 开发**

- **`JSON_TABLE`**：JSON 直接转成关系表；SQL/JSON 构造函数（`JSON`/`JSON_SCALAR`/`JSON_SERIALIZE`）和查询函数（`JSON_EXISTS`/`JSON_QUERY`/`JSON_VALUE`）。
- `MERGE` 支持 `RETURNING` 和更新视图；`COPY` 导出大行最高快 **2 倍**，新增 `ON_ERROR` 容错导入。
- 分区表支持身份列（identity）和排除约束；postgres_fdw 可下推 `EXISTS`/`IN` 子查询。
- 内置**跨平台不可变排序规则提供程序**（builtin，UTF-8 下 C 语义），消除跨平台排序差异。

**高可用 / 升级 / 备份**

- **大版本升级无需删除逻辑复制槽**，免去升级后重新同步。
- 逻辑复制支持**故障切换控制**（failover slots）；新工具 **`pg_createsubscriber`**：物理备库直接转成逻辑订阅者。
- `pg_basebackup` 支持**增量备份**，配合新工具 `pg_combinebackup` 重组全量备份；`pg_dump --filter` 按对象过滤。

**安全 / 监控**

- TLS 新增 `sslnegotiation`（ALPN 注册 `postgresql`）；预定义角色 `pg_maintain`。
- `EXPLAIN` 显示本地 I/O 块读写耗时，新增 `SERIALIZE`/`MEMORY` 选项；报告索引清理进度；新增 `pg_wait_events` 视图。

------

## PostgreSQL 18（2025）

**I/O 与性能（核心）**

- **异步 I/O（AIO）子系统**：后端可排队多个读请求，顺序扫描、位图堆扫描、VACUUM 等受益，存储读取最高 **3 倍**；`io_method` 控制，新视图 `pg_aios`；`effective_io_concurrency` 默认值提到 16。
- 普通 VACUUM 可在全可见页上**提前冻结**部分页面，降低后续全表冻结成本。
- 优化器自动消除不必要的自连接；访问大量关系的锁性能提升。

**索引**

- **B-tree skip scan**：多列复合索引在前导列无等值条件、后续列有条件时也能走索引，同时可优化部分 `OR` 查询。
- 非 btree 唯一索引（如 GIN）可作为分区键、用于物化视图。

**SQL / 类型**

- **虚拟生成列（virtual generated columns）**：读取时计算、不占存储，并成为生成列默认（存储型仍可用 `STORED`）。
- **`uuidv7()`**：时间有序 UUID（利于索引局部性）；`uuidv4()` 别名。
- **时序 / 范围约束**：主键、唯一、外键支持基于范围的约束（`WITHOUT OVERLAPS`）。
- `RETURNING` 在 INSERT/UPDATE/DELETE/MERGE 中支持 `OLD`/`NEW` 别名。
- `crc32()`/`crc32c()`；Unicode 升级到 16.0；`COPY ... REJECT_LIMIT` 限制容忍错误行数。

**升级 / 复制 / 工具**

- **`pg_upgrade` 保留优化器统计信息**（扩展统计除外，可用 `--no-statistics` 关闭），升级后免跑 analyze；新增 `--swap`（目录交换，可能最快）、检查并行化。
- 生成列可逻辑复制；`CREATE SUBSCRIPTION` 的 streaming 默认改为 `parallel`；非活动复制槽可按 `idle_replication_slot_timeout` 自动失效。
- psql 支持 pipeline 反斜杠命令（`\startpipeline` 等）、`\parse`/`\bind_named`。

**安全 / 认证**

- 新增 **OAuth 认证**（`pg_hba.conf` 的 `oauth` 方法、`oauth_validator_libraries`）。
- postgres_fdw/dblink 支持 **SCRAM 凭据透传**（`use_scram_passthrough`）；可配置 TLS 1.3 cipher suites；大对象支持默认 ACL。
- 新扩展 `pg_overexplain`（EXPLAIN 调试细节）、`pg_logicalinspect`；pgcrypto 增加 `sha256crypt`/`sha512crypt` 与 FIPS 相关函数。

------

## 跨版本技术主线（13 → 18）

表格

| 主线              | 演进脉络                                                     |
| ----------------- | ------------------------------------------------------------ |
| **索引**          | 13 B-tree 去重 → 14 btree 主动删条目抑膨胀 / BRIN bloom → 15 NULLS NOT DISTINCT → 17 BRIN 并行构建、IN 优化 → 18 **skip scan** |
| **并行查询**      | 13 并行索引 vacuum、分区聚合 → 14 并行 seqscan I/O、Memoize → 15 DISTINCT 并行 → 16 并行 FULL/RIGHT join → 18 pg_stat 增加并行 worker 统计 |
| **I/O 子系统**    | 14 并行扫描块组分配 → 17 流式 I/O → 18 **异步 I/O 框架（AIO）** |
| **逻辑复制**      | 13 分区表发布 → 15 列清单 / 行过滤 → 16 备库发布、并行 apply、双向 → 17 升级保留槽、failover、pg_createsubscriber → 18 生成列复制 |
| **SQL/JSON**      | 13 jsonpath `.datetime()` → 14 jsonb 下标 → 16 构造函数 / 谓词 → 17 **JSON_TABLE** 全套 SQL/JSON → 18 虚拟生成列配合 |
| **VACUUM / 冻结** | 13 并行索引 vacuum、插入触发 → 14 failsafe、可跳过索引 → 16 减少必要性冻结 → 17 内存降 20× → 18 可见页提前冻结 |
| **压缩 / 备份**   | 14 TOAST LZ4 → 15 zstd + 服务端备份压缩 → 17 **增量备份** + pg_combinebackup |
| **安全认证**      | 13 TLS1.2、channel binding → 14 SNI/DN → 15 public schema 收紧 → 16 require_auth / 负载均衡 → 17 ALPN、pg_maintain → 18 **OAuth**、SCRAM 透传 |
| **可观测性**      | 13 plan 时间 → 14 pg_stat_wal/backend_memory → 15 统计入共享内存、jsonlog → 16 **pg_stat_io** → 17 pg_wait_events、EXPLAIN I/O → 18 pg_aios、字节 / WAL 维度 |
| **大版本升级**    | 15 pg_upgrade 保留 OID/relfilenode → 17 逻辑槽保留 → 18 **保留优化器统计、--swap** |

**升级建议（内核视角）**：13/14 已在 2025 年末结束社区支持，生产应至少升 15+；若关注向量 / 高并发检索链路，16 起逻辑复制能力和 17 的增量备份、18 的 AIO 与 skip scan 是最有价值的三个跨越点。