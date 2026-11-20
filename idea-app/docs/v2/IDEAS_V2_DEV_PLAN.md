# IDEAS V2.0 开发计划

- 基线：现有 Flutter + FastAPI + SQLAlchemy + PostgreSQL/SQLite 项目
- 功能分支：feature/ideas-v2-foundation
- 节奏：4 个两周 Sprint 为初始估算；实际工期以团队人数、部署环境和测试结果为准。

## 1. 技术基线（已读取仓库）

- FastAPI 入口统一注册 `/api` 路由；JWT 鉴权和限流已存在。
- ORM 已有 Idea、ForkRelation、VaultItem、Notification 等模型。
- fork_relations 已支持 fork / merge / evolve；Collide confirm 当前创建两个父关系。
- Idea 当前 status 为 active/fading/faded/rejected；不能把 status 当成公开/私有字段。
- DB 初始化脚本位于 `idea-app/backend/db/schema.sql`；文档 DB_SCHEMA / DATABASE_DESIGN 与 ORM/SQL 有版本差异。
- Flutter 已有 Explore、Create Idea、Idea Detail、Fork Guide、LineageTree；LineageTree 已支持多父节点布局。
- 当前仓库读取到的测试目录包含 conftest、并发测试、Spark AI 测试；尚未执行测试。

## 2. 关键风险与设计策略

1. 私有默认：增加 publication_status + visibility；服务端所有公开查询过滤。
2. 授权选择：is_forkable 只保留兼容，不再单独代表许可；历史记录用 legacy_unspecified，不自动扩大授权。
3. 现有关系复用：扩展 fork_relations，不平行创建重复的 idea_relations 表。
4. DAG：自环可由 CHECK 拦截；多行环必须由事务中的递归可达性检查和并发锁处理。
5. Explore：当前热门与随机查询可能重复，V2 需去重并增加公开过滤。
6. 缓存：发布、撤回、授权变更必须失效公开缓存；私有和公开缓存隔离。
7. SQLite：PG JSONB、递归 CTE、锁实现不能默认兼容 SQLite，需单独实现或明确协作写能力仅支持 PG。
8. 迁移：生产 schema 未直接访问，迁移脚本只是待评审提案；执行前需备份并与部署库 diff。
9. 旧客户端：创建接口切换为草稿后，Flutter 必须同步更新，避免旧 UI 的“发布”按钮语义错位。

## 3. Sprint 0 — 基线核查与产品冻结（当前阶段）

已完成：
- [x] 创建功能分支。
- [x] 核对 README、API_SPEC、DB_SCHEMA、DATABASE_DESIGN、schema.sql。
- [x] 核对 Idea/ForkRelation ORM、Idea API、Collide/Evolve、Vault、Auth、Settings。
- [x] 核对 Flutter 创建页、Fork 页面、详情页和血缘组件。
- [x] 确认产品基线：默认私有、发布后公开；作者自行选择授权；先做异步协作。

待补充：
- [ ] 检查全部 Pydantic schema、notifications/spark 路由和测试 fixture。
- [ ] 检查 Flutter API service/provider 对响应字段的依赖。
- [ ] 确认部署库 schema、SQLite 支持范围和当前备份/回滚流程。
- [ ] 产品负责人确认历史内容过渡规则、授权文案、撤回后的衍生节点策略。

交付：四份 V2.0 基础文档 Draft 1.0（本 PR）。

## 4. Sprint 1 — Idea 权限、发布与关系底座（约 2 周）

### Backend
- 新增 publication_status、visibility、license metadata、published_at。
- 建立统一权限服务：can_view / can_publish / can_fork / can_collide。
- 新增草稿编辑、发布、撤回 API。
- Explore、详情、Vault、用户主页加入权限过滤。
- Fork/Collide/Evolve 授权校验。
- 关系服务：DAG 防环、事务和并发锁。
- 局部血缘 API：深度、节点数限制、权限过滤。
- 增量迁移、迁移前后校验和审计。

### Flutter
- Create Idea 改为私有草稿。
- 发布设置页：可见性、授权、Fork 开关、确认条款。
- Idea Detail 展示发布状态、授权和来源。
- Explore / Profile / Vault 权限态与错误态。
- LineageTree 展示关系类型。

### 验收
- 游客无法读取私有 Idea；私有内容不出现在 Explore、公开主页和公开图谱。
- 公开发布需要作者显式确认和有效授权。
- 不允许改编的授权会在服务端阻断 Fork/Collide/Evolve。
- 双父 Merge 关系正确；DAG 自环、简单环和并发环测试通过。
- 旧数据和旧客户端回归测试通过。

## 5. Sprint 2 — 多人异步协作（约 2 周）

Backend：协作项目、成员邀请/接受、贡献提交/审核、贡献者归属、事件时间线、协作发布事务。
Flutter：协作创建、邀请成员、协作详情、贡献编辑、Owner 审核和最终发布。
验收：非成员和 pending invite 无权访问；成员角色正确；贡献可追溯；只有 Owner 发布；发布失败整体回滚。

## 6. Sprint 3 — 创意宇宙与图谱体验（约 2 周）

- 局部递归图谱查询和缓存。
- 默认上下游 2 层，最多 3 层，按需展开。
- Inspired 灵感关联与严格血缘关系分离。
- 图谱图例、关系类型、节点跳转和时间线。
- 性能与权限过滤测试。

## 7. Sprint 4 — 社区体验、治理与发布（约 2 周）

- Explore 筛选排序、用户主页贡献记录。
- 通知类型和通知偏好。
- 举报/审核后台（范围需产品确认）。
- 安全、速率限制、缓存隔离、日志和监控。
- 灰度、备份恢复和回滚演练。

## 8. Definition of Done

- 需求、API、ORM、SQL migration 保持一致。
- 服务端权限覆盖所有读写入口。
- 正常、异常、越权、幂等和并发路径有测试。
- 旧 API/客户端兼容方案明确。
- PR 包含变更摘要、测试结果、迁移步骤和回滚策略。
- 不提交密钥、生产数据或个人信息。
- 未经产品负责人批准不合并 main。

## 9. 协作分工

| 角色 | 责任 |
|---|---|
| 产品负责人（用户） | 产品决策、授权条款、范围优先级、验收与合并批准 |
| AI 研发协作（ChatGPT） | 仓库核查、文档、技术拆解、代码提交、测试设计和 PR 说明 |
| 开发/运维环境 | 本地数据库迁移、Flutter build/test、集成测试、部署和备份 |

ChatGPT 可通过 GitHub 连接器直接读写仓库；这不等于已在用户本地运行环境执行 Flutter、PostgreSQL 或部署命令。所有测试只有真实执行后才能标记通过。

## 10. 产品负责人待确认事项

1. 历史 Idea 迁移：全部默认私有并逐条重新发布，还是为既有公开内容设过渡期？
2. 首批授权条款的准确中文文案及法律文本。
3. 私有 Idea 是否允许作者邀请协作者查看原始内容（建议允许明确邀请）。
4. 作者撤回原 Idea 后，已 Fork 的衍生节点是否继续公开（建议保留节点及来源快照，但必须满足原授权约束）。
5. 旧版客户端最低兼容版本和切换窗口。

## 11. 进度记录

- 2026-11-20：创建 `feature/ideas-v2-foundation`。
- 2026-11-20：用户确认默认私有、发布后公开；作者自行选择授权；先做异步协作。
- 2026-11-20：完成第一轮仓库源码核查并创建四份 Draft 1.0 文档。