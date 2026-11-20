# Lance: Efficient Random Access in Columnar Storage through Adaptive Structural Encodings 论文整理

- 作者：Weston Pace, Chang She, Lei Xu, Will Jones, Albert Lockett, Jun Wang, Raunak Shah（LanceDB）
- 来源：arXiv:2504.15247v1 [cs.DB]，2025-04-21
- 研究对象：Lance 2.1 文件格式（论文发表时仍为实验版本）

## 1. 核心结论

列存格式在 NVMe 上随机访问慢，主要原因不在"列存"本身，而在**结构编码**（structural encoding）：嵌套结构、repetition/definition level、validity、offsets 如何被拆成磁盘上的 buffer。

论文的主要发现：

1. Parquet 只要配置得当（8KiB page、关闭字典编码等），随机访问性能比默认配置高 60 倍以上（parquet-rs 默认 5,500 rows/s，调优后 350,000 rows/s）。代价是全表扫描性能和内存（search cache）上要做取舍。
2. Arrow 风格的结构编码在嵌套类型上需要太多次 IOPS，不适合磁盘和云存储上的随机访问。
3. Lance 2.1 按数据宽度在两种结构编码之间切换：大类型用 **full zip**，小类型用 **mini-block**。它在随机访问上与 Parquet 持平或更好，同时不牺牲全表扫描性能，search cache 也更小。

## 2. 背景与动机

### 2.1 新的工作负载

- AI/ML 场景同时需要**顺序扫描**（模型训练、特征抽取，可能有上万列、深度嵌套的 struct/list）和**随机访问**（全文检索、向量检索、RAG）。
- 搜索类负载需要读取不按主键（聚簇索引）排列的小结果集，会产生大量随机 I/O。

### 2.2 存储介质的差异（论文图 1）

| 存储                         | IOPS     | 读粒度特点                                       |
| ---------------------------- | -------- | ------------------------------------------------ |
| S3                           | 几万级   | 小于约 100KB 的读取得不到额外好处，带宽靠大块读  |
| NVMe（Samsung 970 EVO Plus） | 几十万级 | 4KiB（一个扇区大小）的读即可达到最大随机访问吞吐 |

- 传统做法是把数据全部放进内存，成本高。
- 更经济的做法是用 NVMe 做缓存层，例如 WekaFS、JuiceFS；或者用 S3 Express 这类低延迟云存储。现代表格式（MVCC、数据文件只读）很容易做缓存。
- 因此需要重新评估文件格式能否用满 NVMe 的随机 IOPS。此前只有少量工作在向量检索场景下评测过 Parquet/ORC。

### 2.3 问题定义

列存按列存放，按行随机读取至少每列需要一次 IOP。压缩和嵌套结构的编码方式会让情况更糟，常见三种后果：

- 每列需要多次 IOPS；
- 读放大（读取的数据远超需要）；
- 每次访问都有较高的计算（解压）开销。

## 3. 基本概念

### 3.1 文件组成（统一使用 Parquet 术语，论文图 2）

| 概念                                | Parquet                                                      | Arrow IPC (1.5)                   | Lance                                                        |
| ----------------------------------- | ------------------------------------------------------------ | --------------------------------- | ------------------------------------------------------------ |
| row group：一块表数据               | 有，原本用于并行全扫                                         | record batch                      | 没有，相当于整个文件只有一个 row group，并行扫描用别的方式实现 |
| column chunk：一列连续存放的 buffer | 每个 row group 每列一个                                      | 无，所有 buffer 属于 record batch | disk page，一列在文件中可以有多个                            |
| page：column chunk 的小分段         | 有，用于提升压缩效果，含 rep/def level，可带统计信息、bloom filter | 无                                | 2.0 无，压缩有限且不分块；2.1 中 mini-block chunk 大致相当于 page |

- row group 和 column chunk 对随机访问影响不大，但对全扫性能关键。
- page 决定读放大，是随机访问性能的关键因素。

### 3.2 压缩编码分类

- **Transparent（透明）**：值之间没有依赖，知道位置和长度就能单独解出一个值。例：bit packing、FSST、字典编码。
- **Opaque（不透明）**：值之间有依赖，必须解压多个值才能取一个。例：Snappy 等回溯引用类压缩、Parquet 的 delta-length byte array。
- 不透明编码可以按值单独使用，变成透明的。例如 Lance 对每个值单独做 LZ4，每个值是一个独立的 LZ4 frame。
- **Sparse（稀疏）**：存储时去掉 null（null 信息在 validity bitmap 等处另存），节省空间，但难以定位第 i 个值。
- **Dense（稠密）**：null 位置填充占位数据，支持随机定位，但更占空间。

### 3.3 评估标准

- 随机访问：读到单个值需要的 **IOPS 次数**，以及这些 IOPS 中的**读放大**。
- **search cache**：打开文件（或首次查询）时读入并常驻内存的少量辅助元数据，目标约为数据量的 0.1%。只考虑 warm search，即元数据已在内存中，加载成本被多次查询摊薄。
- 全扫：主要看压缩率和需要从磁盘读取的总数据量。全扫一次 IOP 读整个 column chunk，IOPS 次数不是瓶颈。全扫测试中不假设元数据已缓存。

## 4. 结构编码 vs 压缩编码

论文把列式编码分成两个阶段：

1. **结构编码**（structural encoding，也叫 shredding）：把可能嵌套的数组转成一个或多个叶子节点，每个叶子包含一个或多个基本数组/buffer。
2. **压缩编码**（compressive encoding）：对每个叶子数组/buffer 压缩到最小表示。

已有大量工作研究压缩编码（FastLanes 做整数，ALP 做浮点，BtrBlocks 讲级联），但结构编码通常由文件格式隐式决定，很少被单独讨论。论文认为结构编码决定了：

- 一个 column chunk 被转成多少个 buffer；
- 哪些压缩技术可以使用；
- 读取时的读放大和 I/O 调度方式。

记号：`b0, b1, ...` 表示连续的 buffer；`bi[x]` 表示 buffer i 中偏移 x 处的元素（可能是 1 bit 的 validity、1 字节的二进制数据或多字节的长度/i64）；`bi[x..y]` 表示 [x, y) 范围。

## 5. 现有格式的结构编码

### 5.1 Parquet

- 嵌套数组被转成一系列扁平的叶子列。每个叶子列包含：扁平化的值列表（去掉 null，即稀疏）、repetition level buffer、definition level buffer。
- 这些 buffer 按 page 分块压缩。每个 page 自带对应的 rep/def level（论文图 3：二进制列的每个 page 内有长度 buffer b0 和数据 buffer b1）。
- page 被当作不可分割的不透明块，所以 page 内 buffer 数量无关紧要，也可以用稀疏编码和 delta 之类的不透明压缩。
- **page offset index**（论文中作为 Parquet 的 search cache）：记录每个 page 的位置和首行行号。二分查找即可定位行所在的 page。

优点：一次 IOP 读一个 page 就能拿到某行；page 足够小时随机访问很高效，读放大等于 page 大小。

问题：

- Parquet 的压缩较重，CPU 容易忙于解压，难以把磁盘队列打满。
- 对向量这类大类型，page offset index 太占内存（见 7.4）。

### 5.2 Arrow

- 同样转成扁平叶子列，但叶子列是**稠密**的：null 用占位的 garbage bytes 表示。
- 不用 rep/def level。每层 repetition 有一个 offsets 数组，每层 definition 有一个 validity bitmap。
- 没有 page/分块概念。只有覆盖整个 column chunk 的通用压缩，压缩后整个 chunk 变成不透明的。Arrow 文件通常不压缩。

适合内存场景：不压缩时没有读放大、没有解码开销、不需要 page offset index 和 search cache。

不适合磁盘/云存储：嵌套类型和变长类型有多个 buffer，每个 buffer 都要单独读。以 `List<String>`（每层都可为 null）取第 10 个元素为例（论文图 4），需要 5 次 IOPS，分 3 个阶段：

| 阶段 | 读取内容                                                     |
| ---- | ------------------------------------------------------------ |
| 1    | List validity `b0[10]`，List offsets `b1[10:12]`             |
| 2    | String validity `b2[b1[10]:b1[11]]`，String offsets `b3[b1[10]:b1[11]]` |
| 3    | String data `b4[b3[b1[10]]:b3[b1[11]]]`                      |

除非 record batch 极小，这些 IOPS 很难合并；而极小的 record batch 又不利于全扫。

可以在 Arrow 结构编码上叠加透明压缩（例如把 offsets 按元数据中记录的位宽 bit pack）。对简单类型这样能同时兼顾随机访问和全扫。Lance 2.0 原本就打算走这条路，后来发现复杂类型需要的 IOPS 太多才放弃。

## 6. Lance 2.1 结构编码

### 6.1 设计目标

- 定宽列随机访问最多 1 次 IOP；
- 变宽列随机访问最多 2 次 IOPS；
- 性能不随嵌套层数、数据类型大小、所用压缩方式而变化；
- 全扫性能与 Parquet 相当。

基本思路：把一列的各个 buffer "zip"（交织）到一起。大类型严格按这个思路实现，即 **full zip**；小类型逐值交织的计算开销太大，改用更接近 Parquet 的 **mini-block**。两种编码都使用 rep/def level，构造方式与 Parquet 基本一致。

### 6.2 Full Zip 编码（大类型，每值 ≥ 128 字节）

适用于向量 embedding、张量、图片、长文本等。阈值 128 字节/值来自实验测量。这类值很大，可以在每个值上多花些计算而不影响扫描性能；它们通常已经压缩过（embedding、压缩图片），或者不需要大块分组也能压缩得好。

做法：把一个**基本叶子列**的 rep level、def level 和所有 buffer 按值转置成**行优先**顺序，放进同一个 buffer（论文图 5：`rep[0] def[0] b0[0] b1[0] | rep[1] def[1] b0[1] b1[1] | ...`）。注意只交织单个叶子列内部的 buffer；把多个列（例如 struct 的多个字段）交织在一起是另一回事，称为 packing（见 6.4）。数据类型定宽时，zip 后的 buffer 也是定宽的。

**Control word（rep/def level）**

- rep 和 def level 被 bit pack 合并成一个 1~4 字节的 control word。不分块、不做 RLE，因此整个 column chunk 中 control word 宽度固定。每个值前面都有一个 control word，repetition index 指向它作为值的起点。
- control word 本身不再做 bit pack：值至少 128 字节，压缩比不到 1.01x（节省不到 1 字节），还会引入非字节对齐。很少需要超过 1 字节。
- 例：`Struct<List<String>>` 需要 3 bit def + 1 bit rep，control word 为 1 字节。低 3 位是 def：`000` 有效值，`001` null item，`010` 空 list，`011` null list，`100` null struct。第 4 位是 rep：`1` 开始新 list，`0` 延续当前 list。

**Data buffer**

- 定宽布局本身就是单个 buffer，不需要 zip。
- 变宽布局先把 offsets 转成 lengths，长度放在值前面，bit pack 到最近的字节边界，最多 8 字节。
- 论文图 6 给出 `["AB","C"], NULL LIST, NULL STRUCT, [NULL], []`（类型 `Struct<List<String>>`）的完整布局：每个元素依次是 control word、长度、数据。

**压缩**

- 先压缩再 zip，以保留列式压缩的收益。例如字符串先做 FSST，再 bit pack 长度，FSST 符号表放在 disk page 的元数据里。
- 这要求压缩编码必须是**透明的**，否则无法单独定位和解压某个值。
- 定宽类型不能稀疏编码 null：4KiB 的向量为 null 时，control word 后仍要填 4KiB 的占位数据，这样才能由下标直接算出字节范围。变长类型的 null 只需一个 control word。

**Repetition index**

- 变宽值 full zip 后无法直接随机定位。repetition index 是一个 buffer offset 数组（bit pack，不分块），存放在 zip buffer 前面，指向每个顶层元素的 control word（论文图 7）。
- 全扫时不读 repetition index。
- 随机访问：先查 repetition index 得到位置，再读值本身。读一个范围时，可以读 index 的一段（1 IOP），也可以并行读起止两个位置（2 IOPS）。因此不论嵌套多深，随机访问都是 2 IOPS。
- 论文中 repetition index **不放入 search cache**，因为在大规模数据集上它可能太大。

**RLE（尚未在 2.1 实现）**：full zip 也可以支持 RLE。此时 repetition index 每个值记 3 个数：buffer offset、size（定宽时省略）、run offset。读单个值或一个范围仍是 2 IOPS，思路类似 Procella 的 skip table。repetition index 可能比 zip buffer 还大，但全扫不读它，只略微增加存储成本。

### 6.3 Mini-block 编码（小类型）

小类型可以接受一定读放大，换取扫描时更少的计算。

- 把数组分成若干小 chunk，目标是每个 chunk 压缩后占 1~2 个磁盘扇区（4KiB~8KiB）。
- 每个 chunk 包含一个 rep buffer、一个 def buffer 和任意数量的数据 buffer。buffer **不转置**，编解码可以向量化。
- 允许稀疏存储 null，允许不透明压缩，按 chunk 压缩。代价是取单个值必须解码整个 chunk，既有读放大，也有随机访问路径上的计算放大。

与 Parquet page 的差异：

- 每个 page 的额外开销更小；
- buffer 要求 8 字节对齐；
- 基本类型的 fixed-size-list 当作基本类型处理（validity 是另一个 buffer，不属于 rep/def）；
- 不要求每个 chunk 从一个顶层记录开始（list 可以跨 chunk）。

**分块规则**（偏启发式）

- 每个 chunk 的值个数必须是 2 的幂，长度 pad 到 8 的倍数以保证 8 字节对齐。
- chunk 元数据仅 2 字节：12 bit 记录 chunk 中 8 字节字的个数，4 bit 记录值个数的 log2。
- 每个 chunk 最多 4096 个值。这让 search cache 很小（每 chunk 2 字节），也控制了读放大（mini-block 最多 32KiB，通常接近 4~8KiB）。

缺点：

- 高度可压缩的数据会被迫拆成更多 chunk；
- chunk 大小由压缩算法决定，增加了压缩实现的复杂度；
- chunk 与磁盘扇区并不严格对齐；
- 多列时很难选出合适的 chunk 大小。

**Chunk 结构**：先是一个简短的头，然后各 buffer 从 8 字节对齐的地址开始。

- buffer 个数（2 字节）
- 每个 buffer 的大小（每个 2 字节）
- 对每个 buffer：padding 到 8 字节对齐，然后是 buffer 数据
- 末尾 padding 到 8 字节对齐

论文图 8 的例子：248 个可为 null 的字符串、共 4,957 字节数据。头部为 `3, 31, 248, 4957`，后面依次是 b0（def levels）、b1（string offsets）、b2（string data）。

**Repetition index（mini-block 版）**

- 有变长 list 时需要它来确定随机访问要读哪些 chunk。chunk 元数据只记录扁平化后的元素个数，不知道包含多少完整行，而且行可能跨 chunk。
- 按 chunk 存储，每个 chunk N+1 个非负整数，N 为需要支持随机访问的最大嵌套层数。支持 `array[x]` 需要 2 个数，支持 `array[x][y][z]` 需要 4 个数。
- 第 1 个数是从 chunk 开头起完成的顶层 list（即行）数；第 2 个数是最后一个顶层 list 结束后完成的第 2 层 list 数；依此类推；最后一个数是最后一个第 X 层 list 结束后的扁平元素数。
- 设计上支持任意深度，但 Lance 2.1 的读写实现目前只支持一层 list 查找。

### 6.4 Search cache 对比

| 格式             | search cache 开销                                            | 10 亿行大类型列                     |
| ---------------- | ------------------------------------------------------------ | ----------------------------------- |
| Parquet          | page offset index，parquet-rs 中每个 page 20 字节。大值 + 小 page 会变成一值一页 | 约 20 GiB                           |
| Lance full zip   | 无 search cache                                              | 0                                   |
| Lance mini-block | 每 chunk 24 字节（无 repetition index）或 41 字节（有 repetition index），每 chunk 至少 32 个值 | 无 repetition index 时最多 1.28 GiB |

- 压缩编码也可能在 search cache 中放辅助数据，例如字典、符号表。
- 两种格式的 search cache 都还可以压缩。对 Lance 来说很容易，因为磁盘上的 mini-block 元数据本来就是每 chunk 2 字节，而不是 24 字节。

### 6.5 Struct packing

- 把整个 struct 作为一列存储，不拆成叶子列。读多个字段时 IOPS 更少，随机访问吞吐更高；代价是无法只投影 struct 中的部分字段，必须读整个 struct 再丢弃不需要的数据。
- 先对每个字段单独压缩，再把 buffer 打包，保留向量化的列式压缩。
- 约束：packed struct 必须定宽，所以每个字段都要定宽，有一个变宽字段整个 struct 就是变宽列；每个字段必须按相同节奏分块；打包后的类型要足够小，能用 mini-block。
- 极端情况下可以打包整条记录，Lance 就变成了行存。这可能适用于 out-of-core 排序、hash join 等场景。Arrow 缺少标准行存格式，DataFusion 等 Arrow 原生引擎只能用各自的 ad-hoc 行格式。

## 7. 实验方法

**硬件**：Samsung 970 EVO Plus 2TB NVMe，Intel i7-10700K（8 核 16 线程）。实测磁盘峰值为 4KiB 随机读 850K 次/秒，吞吐 3,400 MiB/s。

**库的影响**：公开的 Parquet/Arrow 库往往缺少高效的随机访问 API，按现有 API 测出的结果不能代表格式本身的能力。parquet-rs 默认配置在小标量上只有 5,500 rows/s，调优后达到 350,000 rows/s。

| 被测对象  | 实现方式                                                     |
| --------- | ------------------------------------------------------------ |
| Lance 2.1 | `lance` Rust crate，默认参数，每个文件 1Mi 行，默认 disk page（column chunk）8MiB。直接用文件读写器，绕开 dataset/table 层开销 |
| Parquet   | `parquet-rs`（v54），用 row selectors 做随机访问。自写封装管理多文件，每个 row group 一个线程任务。尝试多种 row group 和线程组合，只报告最优结果 |
| Arrow     | 现有 Arrow IPC API 性能不佳，改用 Lance 2.0 格式，其结构编码接近 Arrow。唯一区别是 2.0 用特殊 offset 表示 null list，而不是单独的 validity bitmap |

**Coalesced access（合并访问）**：两行相距较近时，同一操作内的两次读取可以合并成一次 IOP；时间相近的读取则可能命中 OS page cache，减少 IOPS 但不减少系统调用。论文认为 benchmark 中这种收益常被高估：

- 收益取决于数据类型、数据集行数和压缩率。论文图 9：随机选 100,000 行时命中的 8KiB page 数，在行数达到数十亿时，小标量也几乎无法合并。
- 收益依赖可用的 page cache。benchmark 环境通常独占大量 page cache，而生产环境中大小类型混合访问，内存还要留给 search cache 和二级索引。

因此小类型随机访问实验使用 10 亿行，在保留少量合并收益的同时避免收益过大；大类型在任何规模下合并收益都很小，用较小数据集即可。

## 8. 实验结果

### 8.1 随机访问

测试数据类型（顶层含 10% null）：

| 名称        | 类型                       | 是否重复/定宽 | 平均大小 |
| ----------- | -------------------------- | ------------- | -------- |
| Scalar      | UInt64                     | No/Fix        | 8 B      |
| String      | Utf8                       | No/Var        | 16 B     |
| Scalar-list | List\<UInt64\>             | Yes/Fix       | 40 B     |
| String-list | List\<Utf8\>               | Yes/Var       | 80 B     |
| Vector      | FSL\<Float32,768\>         | No/Fix        | 3 KiB    |
| Vector-list | List\<FSL\<Float32,768\>\> | Yes/Fix       | 15 KiB   |
| Image       | Binary                     | No/Var        | 20 KiB   |
| Image-list  | List\<Binary\>             | Yes/Var       | 100 KiB  |

负载：每次 take 操作并行取 256 个随机下标，持续 10 秒，统计每秒取到的行数。下标不重复，数据规模足以避免合并 I/O 带来明显收益，对应真实搜索场景：数十亿行，二级索引与行序无关。baseline 指磁盘在没有合并 I/O 时的独立测量能力。

**Parquet（论文图 10）**

- 小类型表现强：每行只需一次 IOP 读所在 page（page = 8KiB），所有 buffer 都在这个 page 里。类型越大越接近 baseline。
- 性能高度依赖 page 大小，单次 IOP 的大小很快成为 NVMe 随机访问的决定因素。小 page 时借助合并访问甚至能超过磁盘 IOPS 上限（8KiB 时仅标量能超过，64KiB 时多数类型都能超过），但合并收益抵不过更大 IOP 的代价，性能仍随 page 增大快速下降。
- 实验中关闭了压缩和字典编码，因为这样效果最好。开启压缩后性能为理想值的 88%，影响不大。开启字典编码后只有理想值的 2%，影响很大，而且随机数据本不该走字典编码。论文认为 reader 可以在不改格式的前提下缓解：只对低基数数据启用字典，并把字典 page 放进 search cache（类似 Lance 的做法）。

**Arrow 风格编码（Lance 2.0，论文图 11）**

- 简单类型上超过 Parquet 和 Lance 2.1（原文此处写作 "Lance 2.0"，结合图 11 应为 2.1），但 string、string-list 更差，原因是额外的 IOPS。
- 定宽类型额外读 validity 的代价不明显：合并访问带来很大收益，相当于把 validity bitmap 变成了 search cache 的一部分。
- 深度嵌套实验：每增加一层嵌套，就多一个 validity 或 offsets buffer。Lance 2.1 不会因此增加 IOP，Lance 2.0 每层多一次 IOP。在 S3（IOPS 更贵）上，以及 list offsets 场景下，影响更明显；NVMe 上的 validity 影响较小，因为 validity buffer 小，很适合合并 I/O。

**Lance 2.1（论文图 11、12）**

- 弥补了 2.0 在字符串上的损失，总体与 Parquet 持平或更好。简单类型上略逊于 2.0，但对嵌套层数很稳健。
- 标量上表现偏弱的一个可能原因：mini-block 要解码整个 chunk 才能取一个值。这个开销来自允许 chunk 内使用稠密和不透明编码。
- 图 12 按不同值大小比较：full zip 在所有大小上都更轻量、更快，数据在内存（无 I/O）时差距更大。

**小数据访问的剖析**：Parquet 和 Lance 在小数据访问上都没有用满 NVMe，两个可能根因有待后续研究：

1. 两者都没有让 page 与磁盘扇区对齐，每次 I/O 要读 2~3 个扇区；
2. 都用 `pread64` 系统调用读取，系统调用开销叠加在解压开销上。

可能的改进方向：使用 io_uring 等基于内核 buffer 的 I/O；小类型都走 mini-block 的不透明编码，限制只用透明编码可以减少解压工作。

### 8.2 压缩效果

Lance 使用的压缩方式如下。Parquet 统一使用 Snappy 并开启字典编码。

| 场景       | 数据                | Lance 压缩        |
| ---------- | ------------------- | ----------------- |
| names      | 美国婴儿名          | Dictionary + FSST |
| prompts    | LLM 训练 prompt     | FSST              |
| dates      | TPC-H ship date     | Bitpacking        |
| reviews    | Amazon 评论         | FSST              |
| code       | 源代码              | LZ4               |
| images     | 压缩图片            | LZ4               |
| embeddings | CLIP 图像 embedding | None              |
| websites   | HTML 网页           | LZ4               |

结论（论文图 13，数值为图上目测）：Lance 的结构编码不妨碍压缩，多数场景压缩率与 Parquet 持平或更高。例如 websites 约 5.6x 对 3.4x，names 约 5.5x 对 3.9x，code 约 4.1x 对 3.0x。dates 上 Parquet 略高，约 2.7x 对 2.3x。images 和 embeddings 两者都约为 1x。

Arrow IPC 和 ORC 不参与全扫和压缩比较：两者虽然能在 Arrow 风格结构编码上压缩，但现有实现的压缩方式使随机访问无法进行。用 bit packing、FSST、逐值压缩等透明编码，Arrow 风格也能兼顾压缩和随机访问，但没有理由认为这些方案在压缩率上更好。

### 8.3 全表扫描

同时测量压缩后的磁盘吞吐（看磁盘利用率）和每秒迭代次数（比较真实性能，避免高压缩率但磁盘利用率低的方案被低估）。

**Parquet（论文图 14、15）**

- 测试 page 大小 8/32/64/256 KiB，row group 大小 1Ki/10Ki/100Ki/1Mi 行，每类取最优组合。
- 多数类别只能用到磁盘峰值带宽的一半左右。
- 根因不是 CPU 瓶颈，而是 I/O 调度低效：每个 reader 在"发起 I/O、等待、解码"之间交替，所有线程同时解码时磁盘就空闲了，加线程也解决不了。
- 8KiB page 意外地在除 embeddings 外的所有类别里得分最高，归一化得分 0.997。也就是说，在 NVMe 上 8KiB page 同时适合随机访问和全扫。
- 实验中关闭了 page 级统计信息。小 page 时这些统计对扫描性能和文件大小都很有害。论文认为统计信息不应内联存储在 page 或 row group 中，而应单独存放、按需加载。如果格式本身支持低读放大的随机访问，就没必要内联统计。
- row group 大小很难配置（图 15）：小类型偏好大 row group，大类型偏好小 row group，但一个文件通常有很多列，只能统一选一个值。dates 列在 1Ki 行的 row group 下直接失败，因为 row group 数超过了 2^16。

**Lance（论文图 16、17）**

- 以 Parquet 在该类别下的最优结果为 1 做归一化，按每秒读取文件数计算。几乎所有场景都与 Parquet 持平或更好，names、embeddings、images 约为 2 倍，dates 略低于 Parquet。
- 部分原因是 Lance 更能用满磁盘带宽，并且**一套配置**就能同时满足随机访问和全扫。
- 仍有改进空间：LZ4 场景下 Lance 可能受限于解压 CPU；names、dates 等场景可以更好地调度 I/O。
- 图 17：不受 I/O 限制时，mini-block 扫描明显更快，因为 full zip 的逐值解交织无法向量化，开销大。这也是小类型使用 mini-block 的原因之一。

### 8.4 Struct packing（论文图 18）

- 测试含 2、3、4、5 个字段的 struct，随机数据、小标量字段、不压缩（所以只读一个字段的成本等于读整个 struct）。
- 随机访问全部字段时，packed 的性能随字段数增加下降得慢，unpacked 下降得快。
- 全扫单个字段时，packed 的性能随字段数大致线性下降。
- 结论：struct packing 用单字段扫描速度换整 struct 随机访问速度。

## 9. 结论

- 论文提出**结构编码**的概念，并用它分析现有列存格式的不足和改进空间。
- Lance 结构编码在两种编码间切换，兼顾大小类型；已实现完整的读写器。
- Parquet 和 Lance 风格编码都能在全扫和随机访问上取得不错的性能。Lance 额外具备：更小的 search cache、无需配置 row group 大小、struct packing、list 可以跨 page、嵌套 repetition index。
- Arrow 风格编码在嵌套类型上需要太多 IOPS，尤其在云存储上，随机访问性能不足。
- Parquet 和 Lance 都能较好地利用 NVMe，但都还有提升空间。

## 10. 未来工作

- 针对不同存储环境（内存、NVMe 阵列、S3）或新数据类型和编码（如 variant）设计不同的结构编码。
- 把顶层 struct 整体打包、把 Lance 当行存使用，与常见行存格式对比。
- 对新文件格式和标准的建议：不存在普遍最优的结构编码，不应把单一结构编码"写死"进格式，而应做成可配置策略，避免出现大量单一用途的格式。

## 11. 要点速查

| 问题               | 答案                                                         |
| ------------------ | ------------------------------------------------------------ |
| 随机访问的关键瓶颈 | 结构编码决定的 IOPS 次数和读放大，而不是列存本身             |
| Parquet 怎么调才快 | 8KiB page、关字典编码、关 page 级统计、用 page offset index  |
| Parquet 的代价     | 大类型下 page offset index 占内存（10 亿行约 20GiB），row group 大小难配置，扫描时磁盘利用率只有一半左右 |
| Arrow 风格的问题   | 每层嵌套和每个变长 buffer 都要额外一次 IOP（`List<String>` 取一行需 5 次 IOPS，分 3 阶段） |
| Lance 2.1 怎么做   | ≥128 字节/值用 full zip（行优先交织，配合 repetition index，最多 2 IOPS）；小类型用 mini-block（4~8KiB chunk，每 chunk 2 字节元数据） |
| Lance 的局限       | mini-block 取单值要解码整个 chunk，小标量略逊于 Lance 2.0；未做扇区对齐；pread64 系统调用开销；2.1 只支持一层 list 查找；full zip 的 RLE 未实现 |