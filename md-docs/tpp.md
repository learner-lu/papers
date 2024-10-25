
# tpp

- 题目: TPP: Transparent Page Placement for CXL-Enabled Tiered-Memory
- 会议: ASPLOS'23
- 视频: [ASPLOS'23 - Session 9A - TPP: Transparent Page Placement for CXL-Enabled Tiered Memory](https://www.youtube.com/watch?v=dynwKQ01-ho&list=PLsLWHLZB96VcL5ktU19HfbVjrG1Wx3KVF&index=118)
- 代码: [patch](https://lore.kernel.org/lkml/cover.1637778851.git.hasanalmaruf@fb.com/)

## 研究问题

> 论文试图解决的具体问题是什么?该问题的核心挑战是什么?

- 数据中心应用程序内存需求增加
- 同类服务器设计中的扩展挑战
  - 内存控制器**仅支持单代内存技术**, 即同一代 DDR, 限制了**混搭**不同成本,带宽,延迟的内存
  - 存储器容量的粒度为二次方,这限制了更细粒度的存储器容量大小
  - 每一代 DRAM 的带宽与容量都是有限的
- CXL(CXL 附加慢速内存可以采用任何技术(例如 DRAM、NVM、LPDRAM 等))
- 数据中心工作负载很少会一直使用所有内存 [2,15,48,70,73].应用程序通常会分配大量内存但很少访问它 [48, 56]. 将此冷内存移至速度较慢的内存层可为更多热内存页创建空间, 它还可以通过灵活的服务器设计(具有更小的快速内存层和更大但更便宜的慢速内存层)来降低总体拥有成本(TCO)

## 局限性分析

> 现有研究的主要局限或缺点是什么?

- Nimble [76]针对大页面迁移进行了优化.在迁移期间,它在内存层之间采用页面交换.这会使性能恶化,因为降级需要在关键路径中等待升级.
- 与 TPP 类似,AutoTiereing [47] 和 Huang 等人的工作. [28] 使用后台迁移进行降级,并使用优化的 NUMA 平衡 [22] 进行升级.然而,它们基于计时器的热点页面检测会导致计算开销并且通常效率低下,特别是当页面不经常访问时.此外,他们都没有考虑解耦分配和回收路径.我们的评估表明,这对于内存受限的应用程序在内存压力下保持其性能至关重要.

## 解决方案

> 动机

1. 应用程序工作集可以被卸载到慢速层内存,而不会对性能产生重大影响. 
2. **大部分匿名内存(为程序的堆栈、堆和/或 mmap 调用创建)往往更热,而大部分文件支持的内存往往相对更冷.**
3. 页面访问模式在有意义的持续时间(分钟到小时)内保持相对稳定.这足以观察应用程序行为并在内核空间中做出页面放置决策. 
4. 通过新的(取消)分配,实际物理页地址可以相当快地将其行为从热更改为冷,反之亦然.静态页面分配会显着降低性能

### Chameleon

chameleon 是论文里面提出来的一个工具, **不过没有找到它的开源代码**, 流程如下

![20241007220422](https://raw.githubusercontent.com/learner-lu/picbed/master/20241007220422.png)

- **Collector**:

  Collector 使用 CPU 的 PEBS(Precise Event-Based Sampling)机制采集内存访问事件.它采样最后一级缓存(LLC)未命中的事件,并获取 PID 和虚拟内存地址等数据.为了平衡开销与精度,采样率设置为每200个事件采样一次.
  
  Collector 将所有 CPU 核心分组,在每个小时间段(默认5秒)后,轮换采样不同的核心组.采样数据写入两个哈希表之一,每个时间段结束后,Collector 唤醒 Worker 处理数据,并切换到另一个哈希表存储下一个时间段的数据.
   

- **Worker**:
   Worker 在另一个线程上运行,读取页面访问信息并生成内存访问行为的见解.它将采样记录视为虚拟页面访问,并通过查找相应的物理页面进行虚拟地址到物理地址的转换.Worker 使用64位位图跟踪页面在每个时间段内的活跃状态,并将这些统计数据用于生成内存使用模式报告.处理完成后,Worker 进入休眠状态,直到下一轮的工作周期

简单来说就是 collector 和 worker 在不同周期内在哈希表1/2之间轮换写入采样数据,以及 Worker 如何在处理完数据后休眠并周期性地唤醒以处理新数据.

作者使用 chameleon 测试了几组 benchmark 的内存冷热页面占比, 如下图所示

![20241007225721](https://raw.githubusercontent.com/learner-lu/picbed/master/20241007225721.png)

平均而言,2 Min Hot 也只有 20% 的访问内存是热的.这说明数据中心应用程序访问的内存的**很大一部分在几分钟内保持冷状态**.如果页面放置机制可以将这些冷页面移动到较低的内存层,则分层内存系统可以很好地适合此类冷内存, 印证了动机3

---

作者区分统计了匿名页面和文件页面的冷热情况, 如下图所示, 可以发现保持热状态的匿名(匿名页面)比例高于文件(文件页面)比例.很大一部分匿名页面很热,而文件页面在短时间内相对较冷. 对应动机2

![20241007232746](https://raw.githubusercontent.com/learner-lu/picbed/master/20241007232746.png)

---

作者进一步评估了不同应用使用页面种类随时间变化的曲线

![20241007235446](https://raw.githubusercontent.com/learner-lu/picbed/master/20241007235446.png)

(a): 当Web服务启动时,它将虚拟机的二进制和字节码文件加载到内存中.因此,在开始时,文件缓存占据了内存的很大一部分.随着时间的推移,**匿名使用量缓慢增长,文件缓存被丢弃,为匿名页面腾出空间**

(bc): 缓存应用程序主要使用文件缓存进行内存中查找.因此,文件页面消耗了大部分分配的内存.对于Cache1和Cache2(图 9b-9c),文件比例律徊在 70-82% 左右.虽然匿名和文件的**比例几乎稳定**,但如果在任何时候**匿名使用量增加,文件页面将被丢弃以容纳新分配的匿名**.

(d): 对于数据仓库工作负载,匿名页面消耗了大部分分配的内存－总分配内存的85%是匿名的,其余15%是文件页面.匿名和文件页面的使用大多保持稳定.

可以得出结论, 尽管匿名和文件使用情况可能会随着时间的推移而变化,但应用程序大多保持稳定的使用模式.智能页面放置机制在做出放置决策时应该**了解页面类型**

---

作者评估了冷页面在一定时间间隔后变热的页面比例

![20241008093348](https://raw.githubusercontent.com/learner-lu/picbed/master/20241008093348.png)

对于Web 而言,几乎 80%的页面会在10分钟内被重新访问.这表明Web大多会重新利用早期分配的页面.缓存也是如此—随机卸载冷内存会影响性能,因为大量冷页面会在十分钟的窗口内被重新访问.

数据仓库表现出不同的特征.对于这个工作负载,匿名大多是新分配的在十分钟的时间间隔内,只有20%的热文件页面之前被访问过.其余的都是新分配的.观察:冷页重新访问时间因工作负载而异.分层内存系统上的页面放置应该意识到这一点,并主动将热页移动到较低的内存节点,以避免高内存访问延迟.

从上述观察来看,**分层内存子系统非常适合数据中心应用程序,因为存在大量具有稳定访问模式的冷内存**.

### TPP

TPP 的设计比较经典, 采用 linux 默认的 LRU 机制选择候选降级页面, 将它们放入单独的**降级队列**中,并尝试将它们**异步**迁移到 
CXL 节点

- 页面检测: autonuma(NUMA Balancing)
- 冷热页面分类: LRU
- 页面迁移: 异步(在找到回收候选者后,我们不调用交换机制,而是将它们放入单独的降级列表中,并尝试将它们异步迁移到 CXL 节点)

  > mention: 迁移到 NUMA 节点比交换快几个数量级

如果降级期间的迁移失败(例如,由于 CXL 节点上的内存不足),我们将回退到该失败页面的默认回收机制.由于 CXL 节点上的分配对性能并不关键,因此 CXL 节点使用默认的回收机制(例如,分页到交换设备).如果有多个 CXL 节点,则**根据节点与 CPU 的距离选择降级目标**.尽管可以采用其他复杂的算法来根据 CXL 节点的状态动态选择降级目标,但这种简单的基于距离的静态机制被证明是有效的.

> linux 有 API move_pages() 可以实现页面的迁移
> 
> 有关页面监控的总结见 [telescope](./telescope.md)

**页面回收**

Linux 为节点内的每个内存区域维护三个水印(min, low, high).

- 如果节点的空闲页面总数低于 low_watermark, Linux 会认为该节点面临内存压力并启动该节点的页面回收.在我们的例子中,TPP 将它们降级为 CXL 节点.对本地节点的新分配将停止,直到回收器释放足够的内存以满足 high_watermark.
- sysctl 接口 /proc/sys/vm/watermark_scale_factor 控制水位线

**页面提升**

由于本地节点上的内存压力增加,新页面可能经常被分配给 CXL 节点.此外,降级页面也可能稍后变得热门. 从远程 CPU 访问的页面将迁移到该 CPU 的本地内存节点称为提升.

如果没有任何提升机制,热点页面将始终被困在 CXL 节点中并损害应用程序性能.为了提升此类页面,我们增强了 Linux 的 NUMA 平衡 [22].  CXL 内存的 NUMA 平衡.在 NUMA 平衡中,内核任务定期对每个内存节点上的进程内存子集(默认情况下为 256MB 页面)进行采样.当 CPU 访问采样页时,会生成次要页错误(称为 NUMA 提示错误).

由于对页面进行采样以查找本地节点的热内存会产生不必要的 NUMA 提示故障开销,因此我们**仅将采样限制为 CXL 节点**.

NUMA hint fault 发生时默认的 numa balance 策略会立即将其提升, 但是这些升级后的页面可能又会马上降级, 导致抖动

为了解决这个问题, 应该在操作系统维护的 LRU 列表中的位置来检查页面的年龄.

- 如果故障页面处于 inactive LRU,我们不会立即考虑该页面进行升级,因为它可能是不经常访问的页面.
- 仅当在active LRU 中找到故障页面时,我们才将其视为升级候选页面.这大大减少了提升的流量.

操作系统通过使用 LRU(最近最少使用)列表进行内存回收.当内存节点没有压力且回收未触发时,inactive LRU 列表中的页面不会自动移动到active LRU 列表.由于 CXL 内存节点不总是处于压力状态,故障页面经常停留在inactive LRU 列表中,从而绕过了页面升级过滤器.

为解决这个问题,当在inactive LRU 列表中发现故障页面时,会将该页面标记为已访问,并**立即将其移到active LRU 列表中**(如第 2 步所示).如果在下一次 NUMA 页面故障提示时页面仍然处于"热"状态,它将保留在 active LRU 列表中,并被提升到本地节点(第 3 步所示).这种做法为 TPP 增加了一些滞后性.

Linux 对匿名页面和文件页面**分别维护独立的 LRU 列表**,因此不同类型的页面根据其 LRU 大小和活跃度具有**不同的提升速率**.这加速了热页在跨内存节点中的收敛过程.

![20241011154132](https://raw.githubusercontent.com/learner-lu/picbed/master/20241011154132.png)

> [!QUESTION]
> 这个问题在 MGLRU 中还存在么?

## 实验

> 实验是如何设计的? 结果如何证明了论文方法的有效性?是否有对比实验?

以应用的带宽作为性能指标, 不涉及磁盘 swap

CXL 用的 FPGA, 测试了两种内存比例, 本地:CXL 2:1 & 1:4

> [!NOTE]
> 这篇论文的实验部分做的有点迷, 我没太看懂, 一直在讨论 traffic 

将活动 LRU 页面视为升级候选者有助于 TPP 为页面升级添加滞后.这使得页面提升率降低了11倍.随后升级的降级页面数量也减少了 50%.虽然降级率下降了4% (figure 18)

> [!QUESTION]
> MGLRU 中的 refault 策略是不是会更好

## 个人思考

> 阅读论文时,有没有引发你思考出新的问题或有待解决的挑战?

作者评估了几个场景下的冷热页面, 页面种类的变化数据, 可以深入探究一下虚拟化场景下的内存冷热页面占比

降级页面的选择可以采用更好的 MGLRU, 可以对比一下 LRU 和 MGLRU 的差距

> [telescope](./telescope.md)
>
> Characterizing Emerging Page Replacement Policies for Memory-Intensive Applications: 探究 MGLRU 性能

迁移节点的选择只考虑了距离

---

## 摘抄

> Introduction

The surge in memory needs for datacenter applications [12, 61], combined with the increasing DRAM cost and technology scaling. challenges [49, 54] has led to memory becoming a significant infrastructure expense in hyperscale datacenters. Non-DRAM memory technologies provide an opportunity to alleviate this problem by building tiered memory subsystems and adding higher memory capacity at a cheaper $/GB point [5, 19, 38, 39, 46]. These technologies, however, have much higher latency vs. main memory and can significantly degrade performance when data is inefficiently placed in different levels of the memory hierarchy. Additionally, prior knowledge of application behavior and careful application tuning is required to effectively use these technologies. This can be prohibitively resource-intensive in hyperscale environments with varieties of rapidly evolving applications.

> 数据中心应用对内存需求的激增[12, 61],加上 DRAM 成本和技术扩展方面日益严峻的挑战[49, 54],导致内存成为超大规模数据中心的一项重要基础设施开支.非 DRAM 内存技术提供了一个缓解这一问题的机会,即建立分层内存子系统,以更低的美元/GB 点增加更高的内存容量[5, 19, 38, 39, 46].不过,这些技术的延迟比主存储器要高得多,而且当数据被低效地放置在存储器层次结构的不同层级时,会显著降低性能.此外,要有效使用这些技术,还需要事先了解应用行为,并对应用进行仔细调整.在拥有各种快速发展应用的超大规模环境中,这种资源密集程度可能令人望而却步.

However, Linux's memory management mechanism is designed for homogeneous CPU-attached DRAM-only systems and performs poorly on CXL-Memory system. In such a system, as memory access latency varies across memory tiers

> 对 CXL 优势的介绍

CXL for Designing Tiered-Memory Systems. CXL [7] is an open, industry-supported interconnect based on the PCI Express (PCIe) interface. It enables high-speed, low latency communication between the host processor and devices (e.g., accelerators, memory buffers, smart I/O devices, etc.) while expanding memory capacity and bandwidth. CXL provides byte addressable memory in the same physical address space and allows transparent memory allocation using standard memory allocation APIs. It allows cache-line granularity access to the connected devices and underlying hardware maintains coherency and consistency. With PCIe 5.0, CPU to CXL interconnect bandwidth will be similar to the cross-socket interconnects (Figure 5) on a dual-socket machine. CXL-Memory access latency is also similar to the NUMA access latency. CXL adds around 50-100 nanoseconds of extra latency over normal DRAM access. This NUMA-like behavior with main memory-like access semantics makes CXL-Memory a good candidate for the slow-tier in datacenter memory hierarchies. CXL solutions are being developed and incorporated by leading chip providers [1, 4, 9, 21, 24, 25]. All the tools, drivers, and OS changes required to support CXL are open sourced so that anyone can contribute and benefit directly without relying on single supplier solutions. CXL relaxes most of the memory subsystem limitations mentioned earlier. It enables flexible memory subsystem designs with desired memory bandwidth, capacity, and cost-per-GB ratio based on workload demands. This helps scale compute and memory resources independently and ensure a better utilization of stranded resources

> 用于设计分层内存系统的 CXL. CXL [7] 是一种基于 PCI Express (PCIe) 接口的开放式、业界支持的互连.它支持主机处理器和设备(例如加速器、内存缓冲区、智能 I/O 设备等)之间的高速、低延迟通信,同时扩展内存容量和带宽. CXL 在同一物理地址空间中提供字节可寻址内存,并允许使用标准内存分配 API 进行透明内存分配.它允许对连接的设备进行缓存行粒度访问,并且底层硬件保持连贯性和一致性.借助 PCIe 5.0,CPU 到 CXL 互连带宽将类似于双插槽计算机上的跨插槽互连(图 5). CXL-Memory 访问延迟也与 NUMA 访问延迟类似.与正常 DRAM 访问相比,CXL 增加了大约 50-100 纳秒的额外延迟.这种类似 NUMA 的行为以及类似主内存的访问语义使得 CXL-Memory 成为数据中心内存层次结构中慢速层的良好候选者. CXL 解决方案正在由领先的芯片提供商开发和整合 [1,4,9,21,24,25].支持 CXL 所需的所有工具、驱动程序和操作系统更改都是开源的,因此任何人都可以直接做出贡献并受益,而无需依赖单一供应商解决方案. CXL 放宽了前面提到的大部分内存子系统限制.它支持灵活的内存子系统设计,根据工作负载需求提供所需的内存带宽、容量和每 GB 成本比率.这有助于独立扩展计算和内存资源,并确保更好地利用闲置资源

