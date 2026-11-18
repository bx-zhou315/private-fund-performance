# 15 分钟讲懂 CalPERS Power BI 项目

项目问题是 **CalPERS 已经从这些基金拿回多少现金，账面价值还有多少，回款变慢会怎样？** CalPERS 是 California Public Employees’ Retirement System。这份公开快照是它在各支基金中的投资记录。Vintage 是 CalPERS 在该基金的首次现金流年份。

## 先用 5 分钟看三个问题

| 报表页 | 你点什么 | 你解释什么 |
| --- | --- | --- |
| Portfolio & Vintage | 选 **Vintage = 2022**，保持两个 Programme | 私募债 12 支，DPI 中位数 0.24x。私募股权 32 支，中位数 0.02x。DPI 衡量每投入 1 美元已经收到多少现金。做跨年份比较时要带上样本数和成熟度。 |
| Manager Due Diligence | 选 **Advent International**，看 GPE IX | TVPI 1.49x，2019 同类合格样本 22 支，中位数 1.53x。DPI 0.40x，约 27% 的总价值已经变成现金。下一步尽调应问剩余投资如何退出、估值依据是什么。 |
| Distribution Timing | 对照两条现金流曲线，读下面的表 | 每一笔分配晚四个季度，出资金额和日期保持原样。TVPI 都是 2.11x。XIRR 由 14.99% 降至 12.43%，下降 2.56 个百分点。KS-PME 从 1.07x 降到 0.94x。 |

当前 Mac 可直接打开 [浏览器展示版](../powerbi/CalPERS-preview.html)。在 Windows 的 Power BI Desktop 里打开 powerbi 文件夹中的 CalPERS.pbip，保留相邻的 Report 和 SemanticModel 文件夹，然后点 **Home → Refresh**。数据快照内嵌，刷新无需登录数据库。需要单文件时可在 Desktop 中 **Save as → .pbix**。

## 用 5 分钟读懂 SQL 到 DAX

1. **SQL 导入与主键**。打开 [calpers_snapshot.sql](../sql/calpers_snapshot.sql)。先用 COPY 加载原始 TSV，粒度是一支基金的一条快照记录。主键由 programme 和 source_row 组成，行号在每个 Programme 内重新开始。
2. **SQL 连接、聚合与排名**。JOIN 接上 Programme 标签和早期基金口径。GROUP BY 按 Programme 和 Vintage 建组，用 percentile_cont 求中位数。窗口函数按同组 TVPI 排名，并处理并列。最后用 LEFT JOIN 把同类排名接回原表，保留早期基金和缺失比率的行。
3. **Power Query 与 Model view**。在 **Transform data** 选 Funds，查看 Advanced Editor。M 读取打包好的快照，提升首行作为表头，设置数字、文本、布尔值和日期。在 **Model view**，沿 Programme → Funds 和 Vintage → Funds 看一对多关系。选 Private Debt 后，筛选沿关系传到 Funds。
4. **DAX 与筛选上下文**。Median DPI = MEDIAN ( Funds[DPI] )。把 Programme 与 Vintage 放进图表或 slicer，Power BI 会在当前筛选范围内计算中位数。SQL 的同类排名是固定快照，切 slicer 不会改写一支基金原本的比较组。
5. **自己验证一遍**。打开 **DAX query view**，逐段运行 [checks.dax](../powerbi/checks.dax) 中的 EVALUATE 查询。检查 485 + 66 条记录、2022 年两组 DPI、以及 XIRR 变化。Power BI 页面上的筛选与 DAX query view 的筛选分别通过 slicer 和 TREATAS 传入。

如果面试官问为什么不直接对所有基金的 DPI 取平均，可以回答 **中位数描述典型基金。SUM(Distributions) / SUM(Paid In) 则按投入金额加权，描述每一美元投入拿回多少。两者回答不同的问题。**

## 面试时可以这样讲

> This project starts with CalPERS’ public private equity and private debt disclosures. I use PostgreSQL to clean the snapshot, reconcile reported multiples and calculate peer statistics. The Power BI model lets me compare fund vintages, review individual manager track records and show how distribution timing affects returns. One finding is that Advent GPE IX is close to its vintage median on TVPI, but only about 27% of its total value has been realised. A separate cash-flow scenario shows how a one-year delay reduces XIRR by 2.56 percentage points while TVPI stays at 2.11x.

你亲手改过筛选器、跑过查询后，再说自己做过哪些操作。若被问到构建过程，可以说明 **AI 协助生成项目文件，你复跑并解释了 SQL、DAX 和报告结果**。原项目另有一个 AI 表格提取小样本试验，共 5 行、40 个字段与原表逐字段比对。

## 会被追问的缩写

| 缩写 | 英文全称 | 项目里的意思 |
| --- | --- | --- |
| LP | Limited Partner | 出资方，此处是 CalPERS |
| NAV | Net Asset Value | 剩余投资的账面净值 |
| DPI | Distributions to Paid-In Capital | 已分配现金 ÷ 已投入资本 |
| RVPI | Residual Value to Paid-In Capital | 剩余 NAV ÷ 已投入资本 |
| TVPI | Total Value to Paid-In Capital | DPI + RVPI，包含已收现金和剩余价值 |
| IRR | Internal Rate of Return | 年化内部收益率。原表披露的 IRR 需要逐笔现金流才能独立复算 |
| XIRR | Extended Internal Rate of Return | 用每笔现金流的实际日期计算的 IRR |
| KS-PME | Kaplan–Schoar Public Market Equivalent | 用公开市场指数给出资和回款作时间加权。1.0x 表示与该基准持平 |
| DAX | Data Analysis Expressions | Power BI 的表达式语言，常用来写随筛选变化的度量值 |
| GPE / SDL | Global Private Equity / Senior Direct Lending | Advent 和 Ares 两个研究案例对应的基金系列 |
