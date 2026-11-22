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

1. 私有默认：新 Idea 增加 publication_status + visibility，默认 draft/private；历史 active 公共 Idea 单独回填为 published/public，进入授权待补充状态。
2. 历史授权过渡：保留既有公开可见性，但授权待补充期间禁止新增 Fork/Collide/Evolve；过渡期长度由产品配置，不能在 SQL 中写死。
3. 授权选择：is_forkable 只保留兼容，不再单独代表许可；历史记录用 legacy_unspecified，不自动扩大授权。
4. 现有关系复用：扩展 fork_relations，不平行创建重复的 idea_relations 表。
5. DAG：自环可由 CHECK 拦截；多行环必须由事务中的递归可达性检查和并发锁处理。
6. Explore：当前热门与随机查询可能重复，V2 需去重并增加公开过滤。
7. 缓存：发布、撤回、授权变更必须失效公开缓存；私有和公开缓存隔离。
8. SQLite：PG JSONB、递归 CTE、锁实现不能默认兼容 SQLite，需单独实现或明确协作写能力仅支持 PG。
9. 迁移：生产 schema 未直接访问，迁移脚本只是待评审提案；执行前需备份并与部署库 diff。
10. 旧客户端：创建接口切换为草稿后，Flutter 必须同步更新，避免旧 UI 的“发布”按钮语义错位。

## 3. Sprint 0 — 基线核查与产品冻结（当前阶段）

已完成：
- [x] 创建功能分支。
- [x] 核对 README、API_SPEC、DB_SCHEMA、DATABASE_DESIGN、schema.sql。
- [x] 核对 Idea/ForkRelation ORM、Idea API、Collide/Evolve、Vault、Auth、Settings。
- [x] 核对 Flutter 创建页、Fork 页面、详情页和血缘组件。
- [x] 确认产品基线：默认私有、发布后公开；作者自行选择授权；先做异步协作。
- [x] 确认历史公开 Idea 保留公开状态并进入授权补充过渡期。
- [x] 确认私有 Idea 支持作者直接邀请，接受后才授权访问。
- [x] 确认撤回父 Idea 不级联删除已有衍生节点，保留署名和创建时授权快照。

待补充：
- [x] 完成 Spark/notifications 路由首轮静态审查；通知读取增加关联 Idea 实时 ACL 过滤（API 级回归测试仍待补）。
- [ ] 检查 Flutter API service/provider 对响应字段的依赖。
- [ ] 确认部署库 schema、SQLite 支持范围和当前备份/回滚流程。
- [x] 产品负责人确认历史公开创意授权补充过渡期为 90 天。\n- [ ] 产品负责人确认授权文案、通知频率及过渡期到期处理。
- [ ] 生产核验：确认当前所有 `status=active` Idea 均确实是既有公开内容，再执行历史数据回填。

交付：四份 V2.0 基础文档 Draft 1.0（本 PR）。

## 4. Sprint 1 — Idea 权限、发布与关系底座（约 2 周）

### Backend
- 新增 publication_status、visibility、license metadata、published_at。
- 建立统一权限服务：can_view / can_publish / can_fork / can_collide。
- 增加私有 Idea 直接邀请/接受/撤销接口及 `idea_access_grants` ACL；协作成员关系不自动等于源 Idea 访问权。
- 历史 active 公共 Idea 回填为 published/public + legacy_license_review_status=pending；过渡期保留读取但阻止新增衍生操作。
- 衍生关系保存来源授权、署名和允许用途快照；撤回父节点不级联删除子节点，按快照判定子节点是否可继续公开/再衍生。
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
- 游客无法读取私有 Idea；私有内容不出现在 Explore、公开主页和公开图谱；直接邀请接受后授权生效，撤销后立即失效。
- 迁移后既有 active 公共 Idea 仍可公开读取，授权待补充期间禁止新增 Fork/Collide/Evolve。
- 公开发布需要作者显式确认和有效授权。
- 不允许改编的授权会在服务端阻断 Fork/Collide/Evolve。
- 撤回父 Idea 不删除既有衍生节点；署名/授权快照存在且控制其公开和后续衍生能力。
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

1. 首批授权条款的准确中文文案及法律文本。
2. 历史授权补充过渡期的具体时长、通知频率和到期处理规则。
3. 旧版客户端最低兼容版本和切换窗口。

## 11. 进度记录

- 2026-11-20：创建 `feature/ideas-v2-foundation`。
- 2026-11-20：用户确认默认私有、发布后公开；作者自行选择授权；先做异步协作。\n- 2026-11-20：用户确认历史公开创意授权补充过渡期为 90 天，自 V2.0 正式启用/公告生效日起统一起算。
- 2026-11-20：补充确认历史公开内容保留公开并进入授权补充过渡期；私有 Idea 可邀请且接受后访问；撤回父 Idea 不删除已有衍生节点，保留署名与授权约束。
- 2026-11-20：完成第一轮仓库源码核查并创建四份 Draft 1.0 文档。

## 12. 历史授权过渡期实施注意事项

- 迁移前先核实线上 Explore/详情的真实公开条件；当前 SQL 草案假设既有 `status=active` 内容此前均公开，必须先用生产数据验证，不能未经核验直接执行。
- 过渡期固定为 90 天，自 V2.0 正式启用/公告生效日起统一起算；部署配置提供统一截止时间，迁移脚本不硬编码日期。站内通知/邮件节奏和到期处理策略仍待产品负责人确认。
- `legacy_license_review_status=pending` 的历史公开 Idea 可读但不能新建衍生节点；作者补充并确认授权后转为 `confirmed`，再按新授权策略开放相应操作。
- 作者撤回父 Idea 后，子节点不级联删除。按每条来源关系保存的授权快照决定是否可继续公开和再衍生；快照缺失/含糊时先限制公开传播并进入人工审核。
- 私有 Idea 的直接访问 ACL 与协作项目成员表分离。所有内容、版本、附件、评论和血缘查询必须统一执行 ACL 检查。


## 13. Sprint 1 实施进展（2026-11-20）

已提交到本功能分支：
- [x] Idea ORM 增加 publication_status、visibility、license、allow_fork 和 legacy review 字段。
- [x] 新增 IdeaAccessGrant 模型及统一查看/衍生权限服务。
- [x] Explore、详情和血缘查询增加权限过滤；Explore 缓存按用户、limit、offset 隔离。
- [x] Fork、Collide、Evolve 在执行前校验授权，并保存来源授权快照。
- [x] 新增发布、撤回、私有 Idea 邀请、接受和撤销 API。
- [x] Vault 收藏校验访问权；移除 VaultItem 不再物理删除 Idea；Vault 列表和计数过滤已撤销的私有访问。
- [x] 新增 PostgreSQL 手动迁移脚本及 SQLite 既有库增量列迁移/一次性历史回填逻辑。
- [x] 新增权限服务测试用例（尚未执行）。

仍待完成：
- [ ] 审查 PostgreSQL migration 与线上 schema/data 的差异，执行前完成备份和 preflight。
- [ ] 执行 pytest 并修复失败用例；补充 API 级越权、缓存隔离、撤销和并发测试。
- [ ] 继续审查其他直接读取入口及通知生成端；补充通知撤权后的 API 回归测试。
- [ ] Flutter API client、创建/发布页面和详情授权 UI 改造。
- [ ] 法律授权文案、90 天通知节奏和到期处理规则确认。
- [ ] 在实际部署环境验证 PostgreSQL/SQLite 升级、回滚和旧客户端兼容。


### 13.1 ACL 边界复审补充（2026-11-20）

- [x] 通知列表按关联 Idea 实时校验访问权，避免私有访问撤销后旧通知继续泄露内容。
- [x] 未读数按所有可访问未读通知统计，不受当前分页限制。
- [x] Collide 拒绝重复来源 Idea ID。
- [ ] 通知 ACL、分页、撤权场景 API 测试尚未补齐和执行。
- [ ] 其他通知生成端、剩余直接读取入口仍需继续审查。

### 13.2 ACL 与通知查询复审（2026-11-20）

- [x] 通知列表在数据库分页前执行关联 Idea ACL 过滤；未读数在数据库层按相同条件聚合。
- [x] Vault 的被 Fork 统计按当前用户对父 Idea 的可见性过滤。
- [x] 私有 Idea 邀请仅授予读取权限；接受邀请不等于获得 Fork/Collide/Evolve 权利，衍生操作限定为明确公开且授权允许的 Idea。
- [x] 更新权限服务测试，覆盖已接受的私有邀请仍不能衍生。
- [ ] 增加并执行通知分页、撤销邀请后通知隐藏、Vault 统计隔离等 API 回归测试。
- [ ] 在真实测试环境执行 pytest，验证嵌套 EXISTS 查询在 SQLite 与 PostgreSQL 的兼容性。
- [ ] 继续核对通知生成端及其文案，尤其是 idea_id 为空的历史通知。

### 13.3 通知操作与统计侧信道（2026-11-20）

- [x] 抽取通知可见性 SQL 谓词，供列表和标记已读接口共同使用。
- [x] 标记已读接口拒绝更新当前不可见的私有 Idea 通知。
- [x] 新增通知 ACL 数据库测试，覆盖分页、未读数、撤权后操作拒绝。
- [x] Vault 的被 Fork 统计仅计入公开 active 的衍生创意。
- [x] 静态检查通知生成端：当前 Idea 关联通知由 Fork 路由创建并关联 parent Idea。
- [ ] 执行 pytest 和 SQLite/PostgreSQL 集成测试；当前仅提交测试代码。
- [ ] 审计历史 idea_id 为空的通知文案与数据，判断是否存在已脱离资源 ACL 的内容快照。

### 13.4 Flutter V2 首批接入（2026-11-20）

- [x] IdeaDetail / IdeaResponse 模型增加 publication_status、visibility、license、is_forkable / allow_fork 元数据，并为旧响应提供安全默认值。
- [x] IdeaService 增加显式发布、撤回、私有邀请、接受邀请和撤销邀请 API 方法。
- [x] 新建创意页面改为“保存草稿”，明确提示默认私有，不再误导为立即公开发布。
- [x] 新增发布设置页面：公开范围、授权类型、自定义授权说明、衍生许可开关和明确条款确认。
- [x] 详情页展示发布状态和授权；Fork / 碰撞 / 演化入口按服务端 is_forkable 控制。
- [x] 详情页仅在当前用户是作者且内容为草稿时显示发布设置入口。
- [x] 新增 Flutter 模型解析测试，覆盖旧 API 默认私有和 V2 授权字段。
- [ ] Flutter test / analyze / build 尚未运行；邀请成员管理 UI、撤回发布 UI 和完整端到端流程仍待完成。

### 13.5 私有创意邀请闭环（2026-11-20）

- [x] 后端新增当前用户待处理邀请收件箱。
- [x] 后端新增私有创意所有者的邀请记录查询。
- [x] 后端新增拒绝邀请接口；接受时再次确认创意仍为私有且未被拒绝。
- [x] 撤销访问权后清理受邀者 Vault 缓存，接受邀请后清理相关详情 / Vault 缓存。
- [x] Flutter 新增邀请收件箱，支持接受和拒绝。
- [x] Flutter 新增私有创意协作者管理页，支持按用户 ID 邀请、查看状态和撤销访问权。
- [x] 详情页和通知页增加入口。
- [x] 新增后端邀请生命周期测试，覆盖 pending → accepted → revoked、declined、访问权变化，以及创意转为公开后拒绝接受过期邀请。
- [ ] pytest / Flutter test / analyze / build 尚未运行。
- [ ] 当前邀请角色用于区分 viewer / contributor 访问级别，但完整异步贡献提交、版本记录和贡献合并工作流仍未实现。

### 13.6 异步贡献第一阶段（2026-11-20）

- [x] 新增独立 idea_contributions 数据模型和 PostgreSQL 手动迁移 002。
- [x] Contributor 必须接受 contributor 邀请后才可提交；Viewer 不可提交。
- [x] 新增贡献提交、列表、编辑、撤回和作者审核接口。
- [x] 贡献列表按权限隔离：作者查看全部，Contributor 仅查看自己的记录。
- [x] 贡献内容提交和编辑接入现有内容审核与审计日志。
- [x] 贡献状态进入审核后锁定；采纳不会自动覆盖源 Idea。
- [x] Idea Detail 返回当前用户 access_role。
- [x] Flutter 新增异步贡献页面，支持提交、查看和作者采纳/拒绝。
- [x] 新增后端贡献权限/流程测试及前端 access_role 解析测试。
- [ ] pytest / flutter test / analyze / build 尚未运行。
- [ ] 贡献采纳后的版本草稿、版本差异、最终发布事务和贡献署名展示尚未实现。
- [ ] PostgreSQL Migration 002 尚未执行。


## 13.7 版本草稿、发布与贡献归属（第一阶段）

- [x] 新增 IdeaVersion / IdeaVersionContribution ORM 模型与 migration 003。
- [x] 作者创建版本草稿，保存最终内容快照、变更说明和贡献选择。
- [x] 作者编辑草稿；草稿中的贡献选择可调整。
- [x] 作者发布版本：事务内更新版本状态、Idea.content、发布者和时间。
- [x] 固化贡献作者 ID、用户名、贡献内容快照；数据库唯一约束限制贡献只归属一个版本。
- [x] 新增版本历史查询 API 和 Flutter 版本管理页面初版。
- [x] GitHub Actions 后端 pytest：40 passed（2026-11-20，包含贡献反向追溯测试）。
- [x] Flutter test：通过（2026-11-20）。
- [ ] Flutter analyze（配置为不因既有 info 提示失败）和 Android Debug build 正在重新验证；migration 003 尚未执行。
- [ ] 需要在真实 PostgreSQL 测试库验证并发版本号分配、事务回滚和唯一约束。


## 13.8 版本历史与贡献反向追溯（第二阶段）

- [x] 贡献列表 API 返回贡献对应的已发布版本信息和冻结署名快照。
- [x] 版本历史展开查看最终内容、发布时间、变更说明和逐条贡献快照。
- [x] 贡献记录跳转到具体版本并自动展开。
- [x] 已被已发布版本消费的贡献在新草稿选择器中禁用。
- [x] 增加贡献反向追溯 API 回归测试。
- [x] 修复 CI Android 构建基础设施：Gradle Wrapper 从 9.1.0 升级到 Flutter 当前要求的 9.3.1。
- [x] 最新 CI 后端 pytest：40 passed；Flutter test/analyze 和 Android Debug build 正在执行/等待本轮最终结果。
- [ ] PostgreSQL migrations 001/002/003 尚未执行，仍需测试库验证事务和约束。


## 13.9 版本差异对比（第三阶段，2026-11-20）

- [x] 新增作者专属版本差异 API：比较同一私有 Idea 下两个不同的已发布版本。
- [x] 差异按字符级片段返回 equal / insert / delete / replace，适配当前 300 字内容上限及无换行短文本。
- [x] 拒绝比较相同版本、草稿版本、其他 Idea 的版本；非作者请求统一返回 404。
- [x] Flutter IdeaService 增加版本比较请求。
- [x] 版本历史卡片增加“与上一版本对比”入口，差异弹窗分别标识新增和删除文本。
- [x] GitHub Actions run 44750312739：后端 41 passed、Flutter test/analyze 和 Android Debug APK 均通过。
- [ ] 仍需补充 Flutter UI 交互测试，以及真实 PostgreSQL migration / 并发事务验证。


## 13.10 贡献者公开主页记录（2026-11-20）

- [x] 新增 `GET /api/users/{user_id}/contributions`，支持 limit/offset 分页。
- [x] 仅返回已发布版本中、所属 Idea 当前仍为 published + public + active 的冻结署名。
- [x] 私有 Idea、版本草稿、撤回或非 active Idea 的贡献不会出现在公开贡献记录中。
- [x] Flutter UserService / Riverpod provider 接入贡献记录查询。
- [x] 个人主页新增“贡献记录”区域，可查看版本快照、变更说明和本人贡献文本，并跳转至对应 Idea。
- [x] 新增后端回归测试，覆盖公开版本、私有 Idea 和草稿关联的隔离。
- [x] 最新 GitHub Actions run 44751593189：Backend 42 passed、Flutter test 和 analyze 通过。
- [ ] Android Debug APK build 仍在运行，待最终确认。
- [ ] 当前页面为登录用户的“我”主页接入；公开查看其他用户主页的导航入口不在本阶段范围。
- [ ] PostgreSQL migrations 001/002/003 仍未执行。


## 13.11 公开创作者主页与公开版本时间线（2026-11-20）

- [x] 新增 Flutter `PublicUserProfileScreen`，复用公开用户主页和公开贡献记录 API。
- [x] 新增 `/user/:id` 路由，并允许未登录访问；后端用户主页与贡献记录 API 均只返回公开数据。
- [x] 创意详情作者卡片可点击进入对应公开主页。
- [x] 新增只读 `GET /api/ideas/{idea_id}/versions/public`，只返回当前公开 active Idea 在 `Idea.published_at` 当日及之后发布的版本及冻结署名；私有阶段版本不追溯公开。
- [x] 新增只读 Flutter 版本时间线页面，展示版本内容、变更说明、发布时间和贡献署名；署名作者可进入公开主页。
- [x] 公开创意详情增加“版本时间线”入口；公开主页的贡献卡片跳转到对应创意时间线。
- [x] 新增后端测试，覆盖公开 Idea 的 published 版本可见、私有 Idea 不可访问。
- [ ] 本阶段新增 Flutter 页面和 API 的最新 CI 尚待确认。
- [ ] 贡献记录目前每次请求默认展示前 20 条；前端“加载更多”分页交互尚未实现。
- [ ] PostgreSQL migrations 001/002/003 仍未执行。



### 13.12 公开创意持续版本管理（产品决策确认：2026-11-20）

- [x] 产品负责人确认公开创意作者可在发布后持续创建、编辑和发布新版本。
- [x] 后端版本管理权限边界调整：作者可管理私有工作态创意，以及 active + published + public 创意；其他用户统一 404。
- [x] 公开版本发布只更新 Idea.content 与版本快照，不改变 visibility、publication_status、license、allow_fork 或 Idea.published_at。
- [x] 版本列表与差异对比保持作者专属；公开时间线仍只展示创意公开后发布的版本，私有阶段版本不追溯公开。
- [x] Flutter 创意详情页对作者显示公开创意的版本管理入口。
- [ ] 对本轮代码变更运行 CI，确认 Backend、Flutter test/analyze 和 Android Debug APK 全部通过。
- [ ] PostgreSQL migrations 001/002/003 仍未执行。



### 13.13 公开贡献分页与版本时间线深链（2026-11-20）

- [x] UserService 新增保留 `total/offset/has_more` 的分页响应方法，兼容旧列表调用。
- [x] 公开创作者主页实现 20 条分页加载更多、加载中/失败/空状态和刷新。
- [x] 贡献卡片携带对应 `version_id` 跳转到公开版本时间线。
- [x] 时间线支持 `?version={version_id}` 深链，自动展开并滚动定位到指定版本。
- [x] 时间线展示版本发布时冻结的署名与贡献内容；署名仍可跳转对应公开主页。
- [x] 后端回归测试扩展：公开时间线的冻结署名、私有阶段版本过滤、草稿过滤、非 active Idea 404；公开贡献记录分页与非 active Idea 隔离。
- [x] 新增 ASGI HTTP 层契约测试，直接通过公开 API 验证时间线过滤、冻结署名、贡献流分页与私有内容隔离。
- [ ] 对最新代码运行 Backend pytest、Flutter test/analyze 和 Android Debug APK CI。
- [ ] PostgreSQL migrations 001/002/003 仍未执行。


### 13.14 公开版本时间线深链可靠性（2026-11-22）

- [x] 修复深链目标版本位于首屏之外时，懒加载列表可能尚未构建目标卡片、导致无法取得目标 BuildContext 的问题。
- [x] 时间线改为在滚动视口内构建完整版本卡片集合，再通过 GlobalKey + Scrollable.ensureVisible 定位目标版本；适用于当前尚未分页的公开时间线数据集。
- [x] 增加加载请求 generation，忽略刷新或路由参数变化前发出的过期响应。
- [x] 路由复用时，ideaId 或 versionId 变化会重新加载时间线。
- [x] 新增 Flutter widget tests：覆盖第 30 个版本的深链展开/滚动，以及路由切换后加载新 Idea。
- [ ] 本次新增 Flutter widget tests、analyze 和 Android Debug APK build 尚待最新 head 的 GitHub Actions 验证。
- [ ] 若公开版本数量增长到较大规模，应在保留任意版本深链能力的前提下引入可定位的分页/虚拟滚动方案；当前全量构建是为修复现阶段深链可靠性所作的范围内权衡。
- [ ] PostgreSQL migrations 001/002/003 仍未执行。


### 13.15 私有协作到公开署名的 HTTP 端到端验收（2026-11-22）

- [x] 新增 `test_collaboration_e2e_api.py`，通过 ASGI HTTP 客户端串联真实 FastAPI 路由，而非仅直接调用路由函数。
- [x] 覆盖作者邀请、待接受邀请箱、待接受前私有详情 404、接受邀请后访问。
- [x] 覆盖 contributor 修改待审核贡献、viewer 接受邀请后仍不能提交贡献。
- [x] 覆盖作者审核采纳、私有贡献列表读取、作者明确发布创意。
- [x] 覆盖公开创意版本草稿创建、关联已采纳贡献、发布版本、匿名公开时间线读取冻结署名。
- [ ] 最新 head 的 pytest、Flutter test/analyze 和 Android Debug APK CI 尚待完成；新增端到端测试通过前不标记验收完成。
- [ ] 本测试使用 SQLite 内存库与 mock 内容审核，不替代 PostgreSQL 迁移验证、生产鉴权/缓存/审核服务验证。
- [ ] PostgreSQL migrations 001/002/003 仍未执行。

### 13.16 协作权限撤销与版本发布失败路径（2026-11-22）

- [x] 贡献撤回接口现在要求操作者仍持有当前 Idea 的 accepted contributor grant；邀请撤销后，原协作者不能继续通过撤回 API 操作私有贡献。
- [x] ASGI HTTP 端到端测试覆盖有效权限下本人撤回成功、权限撤销后撤回返回 403，以及已拒绝贡献不能编辑或撤回。
- [x] 版本发布前复核关联贡献仍为 accepted；若状态已变化，返回 409，Idea 内容和版本状态保持不变。
- [x] 新增模拟数据库 commit 失败并显式 rollback 的测试，验证 Idea 内容、版本状态、发布时间和署名关联不出现半发布。
- [x] 现有数据库唯一约束确保 contribution_id 只能关联一个版本；同一草稿请求重复传入 contribution_id 会返回 422。多次独立提交仍作为独立提案处理，不以文本相同作为数据库去重条件。
- [x] 最新代码 head b784036c5166e3cdc3ea2aec94cdbc9ffb2efdd0 的 CI run 45007930008：Backend 51 passed，Flutter test 和 analyze passed；Android Debug APK build 当时仍在执行。
- [ ] Android Debug APK build 最终结果待确认；以最新文档提交对应 CI 为最终验证依据。
- [ ] PostgreSQL migrations 001/002/003 仍未执行；当前测试使用 SQLite，不替代 PostgreSQL 并发/迁移验收。
### 13.17 PostgreSQL 迁移 SQL 静态审查（2026-11-22）

- [x] 修复 Migration 001 的 PL/pgSQL `DO` 块：使用完整的 `DO $$ ... END; $$;` 美元引用和块结束分号。
- [x] Migration 002 增加对 Migration 001 记录的前置检查；Migration 003 增加对 Migration 001、002 的前置检查，阻止错误顺序执行。
- [x] 新增 `test_migration_contracts.py`，静态检查事务边界、PL/pgSQL 块结构、迁移依赖、贡献状态约束、外键和版本署名唯一约束。
- [x] 新增重复 contribution_id 的版本草稿测试，确认请求返回 422，且请求事务回滚后不残留草稿。
- [ ] 静态契约测试不等于 PostgreSQL 真实执行；仍需在隔离 PostgreSQL 16 测试库验证 001→002→003、重复执行保护、回滚与约束行为。
- [ ] 当前没有连接生产数据库；migrations 001/002/003 未执行。
### 13.18 PostgreSQL 16 迁移集成测试（2026-11-22）

- [x] 新增 `test_postgres_migrations.py`：在隔离数据库中创建最小旧版基础表，按 001→002→003 顺序真实执行 SQL。
- [x] 验证 active Idea 的历史公开回填、draft Idea 保持 private、三个 migration marker、版本号唯一约束和贡献署名单次归属约束。
- [x] GitHub Actions 新增 `postgres-migrations` job，使用一次性 PostgreSQL 16 service container；不连接生产数据库。
- [ ] 新增 PostgreSQL job 的首次 CI 结果待确认。该 job 成功后可证明迁移在该测试基线可执行，但仍不替代生产备份、数据预检查和发布审批。
- [ ] 生产 migrations 001/002/003 仍未执行。

### 13.19 PostgreSQL 16 迁移与版本并发验证（2026-11-22）

- [x] PostgreSQL 16.16 migration integration run 45009294921：真实执行 migrations 001→002→003，1 passed。
- [x] 同一 exact-head CI run：Backend pytest 55 passed、1 skipped、1 warning；Flutter pub get、test、analyze、Android Debug APK build 均通过。
- [x] 新增 `test_postgres_version_concurrency.py`：在独立 PostgreSQL 测试库中通过两个独立 AsyncSession 并发创建同一 Idea 的版本草稿，验证 Idea 行锁使请求串行，最终仅一个草稿成功，另一个返回 409，版本号保持 1。
- [x] GitHub Actions 新增独立 `postgres-version-concurrency` job，使用独立 PostgreSQL 16 service/database，不与迁移测试共享 schema。
- [ ] 新增 PostgreSQL 并发 job 尚待 CI 实际执行；不能将代码已提交等同于并发测试通过。
- [ ] 当前并发覆盖聚焦“同一 Idea 并发创建草稿”；并发发布/编辑、贡献跨版本竞争仍需进一步专项覆盖。
- [ ] 生产数据库未连接；migrations 001/002/003 未执行。生产上线仍需备份恢复演练、schema/data preflight、迁移审批和回滚预案。

### 13.20 PostgreSQL 迁移失败回滚与并发测试修正（2026-11-22）

- [x] 扩展 PG migration integration：验证 Migration 002 在 001 前执行会失败且不留下 schema marker/table；Migration 001 重复执行会失败；Migration 003 在 002 前执行会失败且不创建版本表；前置迁移补齐后 002/003 可正常执行。
- [x] 首轮并发 CI 暴露测试 fixture 的外键种子顺序问题；已在插入 Idea 前显式 flush owner User，避免将 fixture 错误误判为业务锁问题。
- [x] 首轮失败路径测试暴露 asyncpg 多语句执行失败后连接处于 aborted transaction；已在每次预期失败后显式 ROLLBACK，并在 finally 增加清理保护。
- [ ] 修正后的 exact-head CI 尚待完成；在 PostgreSQL job 实际通过前，不标记迁移失败回滚或并发测试验收完成。
