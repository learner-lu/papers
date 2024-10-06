
# tpp

- 题目: TPP: Transparent Page Placement for CXL-Enabled Tiered-Memory
- 会议: ASPLOS'23
- 视频: [ASPLOS'23 - Session 9A - TPP: Transparent Page Placement for CXL-Enabled Tiered Memory](https://www.youtube.com/watch?v=dynwKQ01-ho&list=PLsLWHLZB96VcL5ktU19HfbVjrG1Wx3KVF&index=118)
- 代码: [kernel patch](https://lore.kernel.org/lkml/cover.1637778851.git.hasanalmaruf@fb.com/)

## 局限性分析

> 现有研究的主要局限或缺点是什么?



## 解决方案

> 动机

1. 应用程序工作集可以被卸载到慢速层内存,而不会对性能产生重大影响. 
2. 大部分匿名内存(为程序的堆栈、堆和/或 mmap 调用创建)往往更热,而大部分文件支持的内存往往相对更冷. 
3. 页面访问模式在有意义的持续时间(分钟到小时)内保持相对稳定.这足以观察应用程序行为并在内核空间中做出页面放置决策. 
4. 通过新的(取消)分配,实际物理页地址可以相当快地将其行为从热更改为冷,反之亦然.静态页面分配会显着降低性能

TPP 具有三个主要组件: 

1. 轻量级回收机制,将较冷的页面降级到慢速层节点;
2. 解耦多 NUMA 系统的分配和回收逻辑,以维持快速层节点上的空闲页面空间;
3. 反应式页面提升机制,可有效识别慢速内存层中的热点页面并将其提升至快速内存层以提高性能.我们还引入了对跨内存层的页面类型感知分配的支持,最好将敏感的**匿名页面分配给快速层,将文件缓存分配给慢速层**.通过这种可选的应用程序感知设置,TPP 可以从更好的起点采取行动,并针对具有某些访问行为的应用程序更快地收敛.

## 实验

> 实验是如何设计的? 结果如何证明了论文方法的有效性?是否有对比实验?



## 个人思考

> 阅读论文时,有没有引发你思考出新的问题或有待解决的挑战?

## 摘抄

> Introduction

The surge in memory needs for datacenter applications [12, 61], combined with the increasing DRAM cost and technology scaling. challenges [49, 54] has led to memory becoming a significant infrastructure expense in hyperscale datacenters. Non-DRAM memory technologies provide an opportunity to alleviate this problem by building tiered memory subsystems and adding higher memory capacity at a cheaper $/GB point [5, 19, 38, 39, 46]. These technologies, however, have much higher latency vs. main memory and can significantly degrade performance when data is inefficiently placed in different levels of the memory hierarchy. Additionally, prior knowledge of application behavior and careful application tuning is required to effectively use these technologies. This can be prohibitively resource-intensive in hyperscale environments with varieties of rapidly evolving applications.

> 数据中心应用对内存需求的激增[12, 61],加上 DRAM 成本和技术扩展方面日益严峻的挑战[49, 54],导致内存成为超大规模数据中心的一项重要基础设施开支.非 DRAM 内存技术提供了一个缓解这一问题的机会,即建立分层内存子系统,以更低的美元/GB 点增加更高的内存容量[5, 19, 38, 39, 46].不过,这些技术的延迟比主存储器要高得多,而且当数据被低效地放置在存储器层次结构的不同层级时,会显著降低性能.此外,要有效使用这些技术,还需要事先了解应用行为,并对应用进行仔细调整.在拥有各种快速发展应用的超大规模环境中,这种资源密集程度可能令人望而却步.

However, Linux's memory management mechanism is designed for homogeneous CPU-attached DRAM-only systems and performs poorly on CXL-Memory system. In such a system, as memory access latency varies across memory tiers