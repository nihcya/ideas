# IDEAS V2.0 — Sprint 1 源码基线审计

> 审计分支：`feature/ideas-v2-foundation`  
> 审计基线：PR #2 head `dce39532165a77d10c06fd9e2fb5a79e3060d252`  
> 范围：后端 ORM、FastAPI 路由、Pydantic schemas、数据库初始化、SQL schema 与现有测试。  
> 本文是代码静态审计记录；未连接生产数据库，未执行应用测试或迁移。

## 1. 结论

当前代码尚未具备安全引入「默认私有 + 显式发布 + 授权约束衍生 + 私有邀请」的条件。主要原因不是单一字段缺失，而是读取入口、衍生入口、缓存和数据库迁移策略均以“所有 active Idea 可公开访问”为前提。

Sprint 1 应先建立统一的 Idea 可见性/授权服务，再逐个接入所有读取和写入路由。不能只在 Explore 页面加过滤。

## 2. 已确认的代码事实与风险

| 优先级 | 文件 | 现状 | V2.0 改造要求 |
|---|---|---|---|
| P0 | `backend/models/idea.py` | Idea 没有 publication_status、visibility、license 等字段；`status` 是 active/fading/faded/rejected 内容状态 | 新增独立发布、可见性、授权及撤回字段；不复用 status |
| P0 | `backend/routers/ideas.py` | Explore 仅按 status=active 查询；详情仅排除 rejected；未校验作者/访问授权 | 所有查询统一过滤公开或当前用户有权访问的 Idea |
| P0 | `backend/routers/ideas.py` | Explore 缓存键仅含 offset，且未区分用户/权限 | 公开内容与用户私有内容分开缓存；或权限查询不缓存；禁止跨用户缓存泄露 |
| P0 | `backend/routers/ideas.py` | Fork 只检查父节点存在、status 和 is_forkable | 检查调用者读权限、父节点发布状态、授权状态、许可是否允许衍生；写入来源授权快照 |
| P0 | `backend/routers/evolve.py` | Collide/Evolve 生成与确认入口直接按 ID 读取父 Idea，未执行访问控制或授权检查 | AI 预览与确认入库均执行权限校验；确认时再次校验并保存每个父节点授权快照 |
| P0 | `backend/routers/vault.py` | collect 仅检查 Idea 存在；可收藏未授权私有内容 | collect 必须验证当前用户访问权限 |
| P0 | `backend/routers/vault.py` | 移除仓库时，在无血缘关系时会物理删除 Idea | 区分“从我的仓库移除”和“作者撤回/归档”；不得因单个 VaultItem 删除而物理删除创意 |
| P1 | `backend/routers/users.py` | 用户公开资料的 circles 从 VaultItem 读取，未过滤公开可见性 | 公开 profile 只返回公开且可展示的 Idea；私有内容仅对有权用户可见 |
| P1 | `backend/models/fork_relation.py` | 仅存 child/parent/type/angle，无授权快照 | 增加 JSON metadata 或独立快照表；快照应记录来源授权版本、作者、时间和允许用途 |
| P1 | `backend/models/__init__.py` | 尚无 IdeaAccessGrant 模型 | 新增邀请/授权成员模型，pending 不授予访问权，接受后生效，可撤销 |
| P1 | `backend/schemas/idea.py` | 创建请求仅有 content；响应无 publication/visibility/license 字段 | 增加发布与授权 schemas；服务端默认 draft/private，不能信任客户端默认值 |
| P1 | `backend/database.py` | SQLite 启动使用 metadata.create_all；PostgreSQL 启动不执行 schema migration | 引入版本化迁移；SQLite 和 PostgreSQL 分别验证升级路径；启动时不静默执行破坏性迁移 |
| P1 | `backend/db/schema.sql` | 当前 SQL schema 与 ORM 为静态初始建表定义，无 V2.0 迁移历史 | 维护可审查、可回滚的增量迁移，不直接覆盖生产 schema |
| P2 | `backend/tests/` | 当前测试主要覆盖并发与缓存，没有私有权限、授权和衍生权限测试 | 增加匿名/作者/受邀者/无关用户矩阵、授权过期、撤回父节点、缓存隔离、并发邀请测试 |

## 3. 必须覆盖的入口

### 读取入口
- `GET /api/ideas/explore`
- `GET /api/ideas/{idea_id}`
- `GET /api/vault`
- `GET /api/users/{user_id}`
- 血缘图中的父节点和子节点查询
- 任何通过 ID 直接读取 Idea 内容的内部服务或后续接口

### 衍生/收藏入口
- `POST /api/ideas/fork`
- `POST /api/ideas/collide`
- `POST /api/ideas/collide/confirm`
- `POST /api/ideas/evolve`
- `POST /api/ideas/evolve/confirm`
- `POST /api/vault/{idea_id}/collect`

Collide/Evolve 的 AI 预览阶段和确认阶段都必须校验，避免用户在权限被撤销后仍使用旧预览结果入库。

## 4. 数据库与迁移阻塞项

1. 仓库当前未发现 Alembic 迁移目录或版本化迁移机制。
2. SQLite 的 `create_all` 只创建缺失表，不会为既有表补列。
3. PostgreSQL 启动路径没有执行 schema migration。
4. V2.0 SQL 草案不能直接作为生产迁移执行；需先验证 FK、索引、默认值、JSON 类型、约束命名和重复执行行为。
5. 必须核实生产环境中 Explore、详情、用户主页等查询的真实公开条件，不能仅凭 `status=active` 推断历史内容全部公开。
6. 历史授权补充过渡期已确认 90 天；系统通过部署配置确定统一截止时间，不应在 SQL 迁移中硬编码具体日期。到期处理规则仍待产品确认。

## 5. 推荐实施顺序

1. 建立可见性与授权领域模型：Idea 发布字段、IdeaAccessGrant、来源授权快照。
2. 建立统一服务：`can_view_idea`、`can_derive_from_idea`、`can_manage_idea`，并统一 404/403 语义，避免泄露私有资源是否存在。
3. 建立迁移：PostgreSQL 版本化迁移 + SQLite 既有库升级脚本；先 dry-run/备份/核验，再执行。
4. 先封闭读取入口和缓存隔离，再接入 Fork/Collide/Evolve/Collect。
5. 实现发布、撤回、邀请/接受/撤销 API。
6. 补充权限矩阵、授权快照、DAG 和回归测试。
7. 最后接 Flutter 页面与 API client，保证旧客户端兼容窗口。

## 6. 本轮未执行事项

- 未连接或读取生产数据库。
- 未执行任何 SQL 或数据迁移。
- 未运行 pytest、Flutter test、build 或部署。
- 未合并 PR #2 或修改 `main`。


## 7. V2 ACL 追加复审（2026-11-20）

本次继续审查 Spark 与通知路由后，发现并修复以下边界：

- `GET /api/notifications`：通知记录可能在私有 Idea 访问权撤销后继续存在。现在按通知关联的 Idea 在读取时重新执行 `can_view_idea`；无法访问或关联 Idea 已不存在的通知不返回。
- 未读数：改为在全部未读通知中重新核验关联 Idea 的可见性，不再错误地只统计当前分页。
- `POST /api/ideas/collide`：拒绝将同一个 Idea ID 同时作为两个碰撞来源，返回 422 `DUPLICATE_SOURCE`。
- `POST /api/spark/submit`：新建 Idea 依赖 ORM 的 `draft/private` 默认值；本次静态检查未发现 Spark 路由直接向其他用户公开读取提交内容的入口。

仍需注意：
- 通知列表当前是在分页取数后过滤不可见记录，单页返回数量可能少于 limit；后续可优化为数据库层 ACL 过滤。
- 对于 `idea_id IS NULL` 的历史通知，服务端已无法可靠追溯其原始 Idea，当前按非 Idea 关联通知处理；如历史通知文案曾内嵌私有内容，需要单独的数据清理策略。
- 本轮为静态代码检查和 GitHub 文件提交；没有运行 pytest、API 集成测试或部署环境验证。

## 8. ACL 复审修正（2026-11-20，后续提交）

本节覆盖第 7 节中通知分页过滤的旧结论：

- 通知关联 Idea 的 ACL 已移至 SQL 查询条件，在 LIMIT/OFFSET 之前过滤；不可见通知不会占据分页位置。
- 未读数使用相同 SQL 可见性条件聚合，避免将全部通知加载到应用层逐条检查。
- Vault 的 forked_by_others 统计现在也受当前用户对父 Idea 的可见性约束，避免私有创意活动通过统计数量泄露。
- 按 PRD 第 4、6、7.4 节，私有 Idea 的邀请只授予授权范围内的读取权限；接受邀请不自动获得 Fork/Collide/Evolve 权利。衍生操作仅允许已发布、公开、active 且明确授权允许的 Idea。协作者贡献应通过异步协作流程提交，而不是直接 Fork 私有源。
- 对应权限服务测试已调整：接受私有邀请后可以查看，但不能将私有 Idea 作为衍生来源。

仍未解决/验证：
- idea_id 为空的历史通知若文案曾内嵌私有内容，当前无法仅凭关联 ID 判断来源，需要历史数据审查/清理。
- 尚未运行 pytest 或 API 集成测试；SQLAlchemy 相关查询需在测试环境实际执行确认。
- 通知列表、Vault 统计的数据库层 ACL 过滤已提交，但不能据此声称 API 回归测试通过。

## 9. 通知操作与统计侧信道复审（2026-11-20）

- 通知列表与“标记已读”现统一调用 services/notification_access.py 的 SQL 可见性谓词。撤销私有 Idea 邀请后，旧通知既不会出现在列表，也不能通过已知通知 ID 被标记为已读。
- 新增 tests/test_notification_access.py，覆盖数据库层分页前过滤、未读数过滤、撤销邀请后隐藏通知不可标记、可见通知可标记等场景。测试文件已提交，尚未运行。
- Vault 的 forked_by_others 统计现在同时约束父 Idea 当前用户可见，以及子 Idea 已发布、公开、active，避免从统计数推断私有衍生创意的存在。
- 通知生成端静态审计：当前检索到的 Idea 关联通知由 Fork 路由创建，保存了 idea_id=parent.id；未发现 Spark 或 Evolve 路由创建通知的代码。
- 历史 idea_id 为空通知仍无法追溯其原始内容来源，需单独审计历史文案或迁移数据。

验证边界：本轮只提交代码和测试；未运行 pytest、SQLite/PostgreSQL 集成测试，也没有 CI workflow run。

## 10. Flutter V2 接入首轮静态复审（2026-11-20）

- 创建页此前将新建 API 呈现为“发布”，但后端创建行为实际是 draft/private。现已改为“保存草稿”，并提示默认仅作者可见。
- IdeaDetail 模型此前忽略后端已返回的 publication_status、visibility、license_code、license_version、is_forkable；现已补充字段和兼容旧响应的默认值。
- IdeaService 已补充 publish/unpublish/invite/accept/revoke 方法；新增发布设置页并接入 /idea/:id/publish 路由。
- 详情页展示公开状态和授权信息，衍生操作按钮由后端 is_forkable 控制，避免仅凭客户端假设展示可用操作。
- 新增 Flutter 模型解析测试；未执行 flutter test、flutter analyze 或 build。
- 邀请成员 UI、撤回发布入口、API 服务测试、旧客户端行为和真实设备验证仍未完成。

## 11. 私有创意邀请流程静态审计（2026-11-20）

- 新增 GET /ideas/invites/inbox：只返回当前用户待处理、仍为私有且未被拒绝的创意邀请。
- 新增 GET /ideas/{idea_id}/invites：仅创意所有者可查看邀请状态，且仅限私有创意。
- 新增 POST /ideas/{idea_id}/invites/{invite_id}/decline。
- 接受邀请时重新检查创意仍为 private 且未 rejected，防止公开状态变化后接受过期邀请。
- 撤销邀请后清理受邀者 Vault 缓存；接受后清理相关缓存。
- Flutter 新增邀请收件箱、管理协作者页和入口。
- 新增 test_idea_invite_workflow.py，覆盖邀请创建、待处理收件箱、接受、拒绝、撤销和访问权变化。
- 注意：viewer / contributor 目前是邀请角色标签与 ACL 记录，受邀者接受后均获得私有 Idea 读取权限；异步贡献提交、版本管理和贡献合并尚未实现。
- 未执行 pytest、Flutter test/analyze/build；上述测试仅已提交，不能视为通过。

## 12. 异步贡献机制静态审计（2026-11-20）

- 新增 idea_contributions，独立保存贡献作者、内容、说明、状态、审核人、审核时间和审核反馈。
- Contributor 必须接受私有 Idea 的 contributor 邀请才能提交；Viewer 不可提交。
- 作者可查看全部贡献；Contributor 只能查看自己的贡献，避免成员间未公开提案互相泄露。
- Contributor 只能编辑/撤回本人 submitted 状态的记录；审核后锁定。
- 仅 Idea 作者可接受/拒绝贡献。
- 提交与编辑内容通过现有 audit_content 审核，并写入 AuditLog。
- 采纳仅改变 contribution 状态，不直接覆盖源 Idea；后续版本管理阶段再纳入版本草稿。
- Idea Detail 新增 access_role；Flutter 新增异步贡献界面。
- 新增 test_idea_contributions.py，覆盖贡献提交、作者审核、Viewer 禁止提交和非作者禁止审核；前端模型测试覆盖 access_role。
- 新增 PostgreSQL 手动迁移 002_idea_contributions.sql；未执行。
- 未执行 pytest、Flutter test/analyze/build；代码与测试尚未通过运行验证。


## 13. 版本管理静态审计（第一阶段）

- 新增版本 ORM 和 PostgreSQL migration 003；不回填历史版本，避免伪造历史快照。
- 版本管理 API 仅允许私有创意作者访问；协作者无版本发布权限。
- 草稿创建/编辑时校验贡献属于当前 Idea 且状态为 accepted；作者提交最终文本，不由系统拼接贡献内容。
- 发布时锁定 Idea 与 draft version，复核贡献状态，在同一事务更新版本和 Idea.content。
- 署名保存 author_id、用户名和贡献文本快照；数据库唯一约束限制 contribution_id 只能归属一个版本。
- 版本发布不修改 visibility、license 或 allow_fork。
- 静态审查不能替代 pytest / PostgreSQL 并发测试；migration 003 未执行，所有自动化测试仍待实际运行。


### CI 验证补充（2026-11-20）
- GitHub Actions 后端 pytest 已通过：39 passed，1 warning。
- Flutter `flutter pub get` 和 `flutter test` 已通过。
- 首次 `flutter analyze` 因项目现存 62 条 info 级提示返回非零；未发现 warning/error 级输出。CI 已调整为 `flutter analyze --no-fatal-infos`，保留 warning/error 失败门槛，正在重新执行。
- Android Debug build 尚待该轮 Flutter analyze 通过后执行。
- PostgreSQL migration 003 未执行。


## 14. 版本历史与贡献归属反向追溯审计（2026-11-20）

- [x] 贡献列表通过左连接版本归属，仅对已发布版本暴露归属关系；草稿阶段关联不会显示为正式归属。
- [x] 版本历史返回冻结的贡献作者名与贡献内容快照。
- [x] 协作者只能在自己的贡献列表看到自己的贡献及其已发布归属；作者可以查看该 Idea 全部贡献。
- [x] Flutter 版本历史展示每条署名与贡献文本，贡献卡片提供版本跳转。
- [x] 已消费贡献不能再次进入新版本草稿选择。
- [ ] 新增反向追溯测试已在 GitHub Actions 通过；后端测试总计 40 passed。
- [ ] PostgreSQL migration 003 尚未执行。
- [x] Android Gradle Wrapper 版本已提升至 9.3.1，以满足当前 Flutter SDK 的最低要求；构建结果待 CI 确认。


## 15. 版本差异对比第三阶段（2026-11-20）

- 新增 `GET /api/ideas/{idea_id}/versions/{version_id}/diff?against_version_id={uuid}`。
- 接口仅允许 Idea 作者访问；两端版本必须属于同一 Idea 且均为 published，草稿和不存在/越权资源统一按 404 处理。
- 使用字符级 SequenceMatcher 返回 equal / insert / delete / replace 片段，避免当前短文本内容均为单行时行级 diff 无法呈现有效差异。
- Flutter 版本历史为每个非最旧版本提供与上一版本对比入口，并以删除/新增文本区分展示。
- 新增后端测试覆盖有效差异、草稿不可比较和非作者不可访问。
- 最新代码已触发 GitHub Actions；该轮 CI 尚未完成，不能据此宣称差异功能已通过测试。
- 所有 PostgreSQL migrations 001/002/003 仍未执行；未连接生产数据库。


## 16. 贡献者公开主页记录审计（2026-11-20）

- 新增 `GET /api/users/{user_id}/contributions`，以 `IdeaVersionContribution` 的冻结署名为数据源。
- SQL 查询同时约束版本为 published、Idea 为 published + public + active；私有创意、草稿版本和撤回/非 active 内容不进入公开结果。
- 返回贡献文本快照、作者名快照、版本号、版本快照内容和发布时间；避免使用当前可变贡献正文覆盖历史署名。
- Flutter 当前“我”主页新增贡献记录列表，支持打开对应 Idea；加载、空态和错误态均有处理。
- 新增测试覆盖公开、私有及草稿记录隔离。
- 需在最新 GitHub Actions 中确认新增后端测试和 Flutter analyze/test/build；未通过 CI 前不标记运行验证完成。
- 未执行 PostgreSQL migrations 001/002/003；未连接生产数据库。


## 17. 公开创作者主页与公开版本时间线审计（2026-11-20）

- `/user/:id` 复用公开用户资料和公开贡献记录 API；路由允许未登录访问，不返回私有 Idea 的贡献。
- 创意详情作者卡片导航到公开主页；主页贡献条目导航到只读公开版本时间线。
- `GET /ideas/{idea_id}/versions/public` 在 SQL 查询前先确认 Idea 当前为 published + public + active，随后只查询 published 版本，且要求版本发布时间不早于 `Idea.published_at`，避免私有阶段快照被追溯公开。
- 版本时间线仅暴露版本内容快照、发布时间、变更说明和版本发布时冻结的贡献署名；不包含草稿版本。
- 贡献署名作者 ID 用于跳转公开主页，不暴露邮箱、认证信息或其他账户资料。
- 新增后端测试覆盖私有 Idea 的 404 隔离；仍需由 CI 确认新增测试和 Flutter 构建。
- 未执行 PostgreSQL migrations 001/002/003。



## 18. 公开主页分页与版本时间线深链复审（2026-11-20）

- 公开贡献记录 API 原已支持 `limit/offset/total/has_more`；Flutter 服务层此前只返回 items，页面也只展示前 20 条。本轮服务层新增完整分页响应，主页增加加载更多和刷新。
- 贡献卡片现在携带正式版本 ID，进入 `/idea/{idea_id}/timeline?version={version_id}`；时间线按 ID 展开并滚动到目标版本。query 参数仅影响 UI 定位，后端公开时间线仍独立执行 Idea 当前公开状态和公开时间边界过滤。
- 时间线页面继续只显示服务端返回的已发布公开阶段版本，贡献作者跳转公开主页；未增加任何匿名访问私有版本管理接口。
- 后端回归测试补充冻结署名、私有阶段版本和草稿过滤、非 active Idea 隔离，以及贡献公开列表分页/has_more。
- 以上代码已提交 PR 分支；最新 CI 尚待执行，不把静态提交视为测试通过。
- PostgreSQL migrations 001/002/003 未执行；未连接生产数据库。


### 18.1 公开发现链路 HTTP 契约测试补充（2026-11-20）

- 新增 `test_public_contribution_api.py`，通过 ASGI HTTP 客户端请求真实 FastAPI 路由，而非只直接调用 Python 路由函数。
- 公开时间线测试覆盖：公开前版本不可见、草稿不可见、当前非 active Idea 返回 404、冻结署名与冻结贡献文本按发布快照返回。
- 公开贡献流测试覆盖：分页参数和 `total/has_more` 契约、冻结署名输出、私有 Idea 贡献不泄露。
- 公开主页前端新增分页加载和版本 ID 深链；深链参数只定位 UI，不改变后端授权边界。
- 代码已提交 PR 分支；必须等待最新 GitHub Actions 确认 pytest、Flutter test/analyze 和 APK build。未连接生产数据库，未执行 migrations 001/002/003。


## 19. 私有协作到公开署名 HTTP 端到端验收（2026-11-22）

- 新增 `test_collaboration_e2e_api.py`，使用 HTTPX ASGITransport 访问真实 FastAPI 路由，并在测试依赖层注入隔离的 SQLite session 与测试用户。
- 覆盖邀请创建、收件箱、pending ACL、接受邀请、详情访问、contributor 提交/编辑、viewer 禁止提交、作者审核采纳。
- 覆盖作者显式公开 Idea、创建版本草稿并关联已采纳贡献、发布版本、匿名读取公开时间线和冻结署名。
- 审核服务与缓存清理在测试中 mock；本测试验证路由、schema、ACL、持久化关系和 HTTP 响应契约，不代表真实外部审核服务或生产 Redis/PostgreSQL 验证。
- 最新 head 的 GitHub Actions 尚待最终结果；在 pytest 通过前不宣称端到端验收通过。
- PostgreSQL migrations 001/002/003 未执行，未连接生产数据库。

## 20. 协作撤权与版本发布异常路径审计（2026-11-22）

- 复审发现贡献撤回 API 原先只校验贡献作者和 submitted 状态，没有复核该用户当前是否仍有 accepted contributor grant；这会使已被撤销邀请的用户仍可操作私有贡献。
- 已在撤回路由补充 _require_accepted_contributor 校验。权限被撤销后撤回返回 403；本人仍有有效协作权限且贡献处于 submitted 时可正常撤回。
- ASGI HTTP 测试覆盖邀请接受、提交、编辑、成功撤回、作者拒绝、拒绝后编辑/撤回锁定、作者撤销邀请、撤权后撤回拒绝，以及后续公开版本署名流程。
- 版本发布时若草稿所关联贡献不再是 accepted，服务端返回 409，且不改变 Idea.content、draft status 或冻结署名关联。
- 模拟 commit 异常后显式 rollback，验证 Idea 内容、版本发布状态、published_at 和 attribution association 均保持发布前状态。
- 贡献重复归属由 uq_version_contribution_consumed_once 数据库唯一约束兜底；请求内重复选择由 _attach_contributions 返回 422。独立重复提交当前允许作为不同提案记录，不按文本相等去重。
- 最新代码 head b784036c5166e3cdc3ea2aec94cdbc9ffb2efdd0 的 Backend CI 为 51 passed、1 warning；Flutter test/analyze 通过，APK build 尚待最终结论。
- 这组测试采用 SQLite 与 mock 审核/缓存；不代表生产 PostgreSQL、Redis 或真实审核服务已集成验收。migrations 001/002/003 未执行。
## 21. PostgreSQL migration 与版本并发安全审查（2026-11-22）

- 发现 Migration 001 的 PL/pgSQL guard 原先写成 `DO $ ... END $;`，美元引用分隔符与块结束分号均不符合 PostgreSQL 语法；已改为 `DO $$ ... END; $$;`。
- Migration 002 现在在创建贡献表前检查 001 的 schema migration marker；Migration 003 在创建版本表前检查 001、002 的 marker，降低人工误执行顺序风险。
- 新增 `test_migration_contracts.py` 静态契约检查，覆盖事务包裹、DO 块、前置依赖、贡献状态 CHECK、FK、版本号唯一约束和 contribution_id 全局唯一约束。
- 新增重复 contribution_id 请求测试：同一草稿重复传入同一贡献返回 422；模拟 FastAPI 请求事务边界 rollback 后不残留 draft。
- 版本号分配与发布均先锁定 Idea 行（PostgreSQL `SELECT FOR UPDATE`），版本草稿行/关联贡献行在编辑和发布路径中也使用行锁；数据库 `UNIQUE(idea_id, version_number)` 与 `UNIQUE(contribution_id)` 作为最终并发约束。
- 当前并发测试主要使用 SQLite，SQLite 不实现 PostgreSQL 行级 `FOR UPDATE` 语义。因此不能将其描述为真实 PostgreSQL 并发验收；需要后续在独立 PG 16 环境运行并发集成测试。
- 本次未运行 SQL migration，也未连接生产数据库。Migration 001 的 active Idea 公共回填仍需上线前按真实生产查询规则做预检查与审批。
## 22. PostgreSQL 16 migration integration coverage（2026-11-22）

- 新增 `tests/test_postgres_migrations.py`，通过 asyncpg 连接独立 PostgreSQL 16 测试库，建立最小旧版 users/ideas/fork_relations 基础表。
- 在真实 PG 16 中按 001→002→003 顺序执行迁移文件，验证 PL/pgSQL dollar-quoted guards、migration markers、active/private 历史回填结果，以及版本号和 contribution_id 唯一约束。
- GitHub Actions 新增独立 `postgres-migrations` job，使用 ephemeral PostgreSQL 16 service container；常规 SQLite pytest 和 Flutter jobs 保持独立。
- 这项测试只证明迁移在最小测试基线上的语法与约束行为，不覆盖生产数据规模、线上 schema drift、备份恢复、锁等待或真实生产回填风险。
- 当前最新提交的 PostgreSQL job 尚待首次运行结果；生产数据库未连接，migrations 001/002/003 未执行。

## 23. PostgreSQL 16 migration CI 实际结果（2026-11-22）

- Exact tested head `5dfdc96b192f058287f174693c551551265c1578` 的 CI run `45009294921` 已全部完成：backend 55 passed、1 skipped、1 warning；PostgreSQL 16.16 migration integration 1 passed；Flutter pub get/test/analyze/Android Debug APK build 全部成功。
- 迁移集成测试使用独立的一次性 CI PostgreSQL 数据库，按 001→002→003 执行；它不代表已在生产数据库执行，也不覆盖生产数据规模、schema drift 或备份恢复。

## 24. PostgreSQL 版本草稿并发测试（2026-11-22）

- 新增 `tests/test_postgres_version_concurrency.py`，使用两个独立 AsyncSession 并发调用真实版本草稿创建路由；使用独立 PostgreSQL 数据库和真实行锁，不以 SQLite 模拟。
- 预期契约：两个请求竞争同一 Idea 行锁；第一个提交一个 draft，第二个在获得锁后观察到现有 draft 并返回 HTTP 409；最终数据库仅存在一个 draft，版本号为 1。
- 新增独立 `postgres-version-concurrency` GitHub Actions job，使用 PostgreSQL 16 service container，与 migration job 隔离。
- 该测试已提交，但其首次 CI 结果尚未确认；不得提前认定并发验证通过。
- 测试数据库通过 ORM metadata 创建/清理 schema，仅供该 disposable CI job 使用；生产数据库未连接、未改动，migrations 001/002/003 未执行。

## 25. Migration failure-path / PostgreSQL concurrency test follow-up（2026-11-22）

- 扩展 PG 16 迁移测试，覆盖 002-before-001、重复执行 001、003-before-002 的拒绝行为，并检查失败事务回滚后 schema marker/table 状态不被部分写入。
- 首次执行暴露两项测试代码问题而非迁移业务缺陷：asyncpg 失败事务需显式 ROLLBACK 后才能继续查询/清理；并发测试种子数据需先 flush User 再插入带 author FK 的 Idea。两项均已修复。
- 修正后的最新 CI 尚在排队/运行；迁移失败路径与 PostgreSQL 并发结果仍 pending，不提前宣称通过。

## 26. PostgreSQL 并发贡献归属竞争修复（2026-11-22）

- 审查 `_attach_contributions` 时发现“先查 attribution 是否存在、再读取 accepted contribution”的 TOCTOU 竞争窗口：两个草稿并发更新可同时观察到贡献尚未归属。
- 现在先锁定目标 `IdeaContribution` 行（`FOR UPDATE`），再检查 `IdeaVersionContribution` 归属。竞争事务等待前一事务提交后，在 READ COMMITTED 下重新执行归属查询并返回 409；数据库唯一约束继续兜底。
- 新增 PostgreSQL 16 集成测试，构造同一 Idea 下两个既有 draft 并发认领同一 accepted contribution，验证只有一个成功且数据库只保留一条 attribution。
- 该新增测试尚待 CI 执行；不能仅凭静态审查宣称竞争场景已通过。

## 27. 生产迁移 runbook 与未执行边界（2026-11-22）

- 新增 `IDEAS_V2_PRODUCTION_MIGRATION_RUNBOOK.md`，将生产迁移的前置条件具体化：只读数据分布检查、历史 active 公开可见性假设确认、schema/object 冲突检查、备份恢复演练、按 001→002→003 执行、迁移后状态与约束校验、应用回滚与数据库恢复策略。
- Migration 001 会将所有 `status='active'` 的 Idea 转为 public/published 并设为 legacy license review pending；这是一项数据政策决策。必须先证明该集合与生产旧版本公开读取规则一致，否则不得执行。
- CI 使用一次性 PostgreSQL 16 数据库；没有访问生产 DB，没有执行生产 preflight，没有执行 001/002/003。真实生产 schema/data/backup/restore 风险仍未验证。

## 28. PostgreSQL 并发发布验证补充（2026-11-22）

- 新增双独立会话并发发布同一 draft version 的 PostgreSQL 16 集成测试。发布路由先锁 Idea 再锁 Version；预期仅一个请求成功，另一个在获得 Idea 锁后发现版本不再是 draft 并返回 404，最终 Idea 内容与发布快照一致。
- 此测试刚提交，尚待 CI 执行验证；不要将预期行为写成已通过结果。


## 29. PostgreSQL 版本编辑与发布并发竞争验收（2026-11-22）

- 新增两个独立 PostgreSQL AsyncSession 并发编辑/发布同一 draft version 的集成测试。
- 锁顺序审查：发布路径先锁 Idea 再锁 Version；编辑路径只锁 Version，不再请求 Idea 行锁，因此不会形成“编辑持有 Version 等待 Idea、发布持有 Idea 等待 Version”的锁循环。
- PostgreSQL READ COMMITTED 下，若发布先完成，等待中的 SELECT ... WHERE status='draft' FOR UPDATE 会在行更新后重新检查条件，编辑请求得到 404；若编辑先完成，发布随后读取已提交的最新草稿快照。
- 验收断言最终版本为 published、published_at 非空、Idea.content 与 content_snapshot 一致，且不存在残留 draft。
- GitHub Actions run [45015839841](https://github.com/nihcya/ideas/actions/runs/45015839841) 的 PostgreSQL concurrency job 已通过，专项文件 **4 passed, 1 warning**；backend pytest 和 PostgreSQL migration job 也通过。Flutter pub get/test/analyze 通过，Android Debug APK build 在记录时仍运行中。
- 新测试运行在独立 PostgreSQL 16 CI 数据库；不代表生产数据库已验证。migrations 001/002/003 未执行。


## 30. 协作贡献审核与邀请撤权并发安全（2026-11-22）

- 协作者写操作在检查 accepted contributor grant 时支持 SELECT FOR UPDATE；提交、编辑、撤回使用行锁保护授权检查与写入之间的事务窗口。
- 作者审核对 IdeaContribution 行执行 SELECT FOR UPDATE，与协作者编辑/撤回串行，避免“审核已接受/拒绝后，旧请求仍覆盖贡献正文或状态”。
- 接受、拒绝和撤销邀请锁定 IdeaAccessGrant 行；创建/重发邀请锁定 Idea 行及已有 grant，降低邀请状态竞争。
- 锁顺序为：协作者写操作先 grant、再 contribution；作者审核只锁 contribution；作者撤权只锁 grant。审核路径不再反向申请 grant 锁，因此没有形成 grant/contribution 反向锁循环。
- PostgreSQL 16 专项测试新增并发编辑 vs 审核、并发编辑 vs 撤权；run [45016633454](https://github.com/nihcya/ideas/actions/runs/45016633454) 的专项文件 **6 passed, 1 warning**。
- 锁定邀请状态后的最新代码 head 由 run [45016696437](https://github.com/nihcya/ideas/actions/runs/45016696437) 验证中；Backend、PostgreSQL migration/concurrency 已通过，Flutter APK build 尚在运行。
- 以上为 disposable PostgreSQL 16 CI 验证，不代表生产数据库已验证；migrations 001/002/003 未执行。


## 31. DAG 来源撤回与衍生授权快照（2026-11-22）

- 所有现有衍生入口均创建新 Idea 作为 child，父节点只能引用已存在的 Idea；API 不允许修改既有关系的 child/parent，因此正常 API 写入保持时间向前的 DAG 结构。Collide confirm 额外拒绝重复父节点。
- Fork、Evolve、Collide confirm 对来源 Idea 行执行 SELECT FOR UPDATE；作者 publish/unpublish 也锁定同一 Idea 行。来源状态变化与衍生关系创建按事务先后串行。
- Collide 的两个来源按 UUID 字符串固定排序后加锁，避免反向选择来源时出现锁顺序死锁。
- ForkRelation.license_snapshot 现在冻结来源 ID、作者 ID/署名、授权代码、自定义授权文本快照、授权版本、创建时间和 allow_fork。
- 详情谱系读取在来源仍可见时展示来源标题；来源撤回后对无权用户展示“已撤回的来源创意”及快照署名，不再展示撤回正文。衍生关系与子创意不因 unpublish 被删除。
- 新增 SQLite API 回归测试验证撤回后的署名保留与重复 Collide 父节点拒绝；新增 PostgreSQL 16 独立会话测试验证 fork 与 unpublish 的行锁串行。
- CI run [45018288819](https://github.com/nihcya/ideas/actions/runs/45018288819)：Backend **57 passed, 9 skipped**；PostgreSQL concurrency **7 passed**；migrations passed；Flutter test/analyze passed，APK build 尚在执行。
- SQLite 测试不验证行锁语义；fork-vs-unpublish 锁竞争由 PostgreSQL 16 专项测试覆盖。以上均不代表生产数据库迁移已执行。


## 32. DAG 来源撤回修复 exact-head CI 结果（2026-11-22）

PR 最新文档/代码 head 的 CI run [45018438622](https://github.com/nihcya/ideas/actions/runs/45018438622) 全部通过：
- Backend：57 passed, 9 skipped, 1 warning。
- PostgreSQL 16 并发：7 passed, 1 warning。
- PostgreSQL migrations：success。
- Flutter tests、analyze、Android Debug APK build：success。
- 该结果验证 CI head，不代表生产 schema/data/备份恢复演练已完成，生产迁移仍未执行。


## 33. 撤回来源的隐私安全谱系与授权展示（2026-11-22）

- API 对仍可访问的来源返回真实 Idea ID；对撤回后不可访问的来源返回 opaque withdrawn:<relation-id>，并标记 is_navigable=false。
- 撤回来源不再泄露私有 Idea ID、原始标题或正文；历史作者署名和授权快照继续保留。
- LineageNode 返回 relation_type 与 license_snapshot；Flutter 模型已解析，LineageTree 禁止跳转不可导航来源，Idea 详情页展示来源授权快照。
- CI run [45019528171](https://github.com/nihcya/ideas/actions/runs/45019528171)：Backend 57 passed, 9 skipped；PostgreSQL concurrency 7 passed；migrations、Flutter tests/analyze 通过；APK build 仍在运行。
- 仍待实现：来源授权对后代节点的传递性限制。尤其多父 Merge 的有效授权应取所有父来源约束交集；custom 授权需明确人工审核/确认，不得默认继承为开放授权。

## 34. 授权继承与多父授权交集实现审查（2026-11-22）

- 授权判断集中在 services/idea_access.py：get_inherited_rights_chain() 汇总所有父关系快照中的完整 rights_chain，并按 source_idea_id 去重；get_effective_rights_chain() 在祖先链后追加当前 Idea 自身授权。
- can_derive_from_idea() 对直接来源和每一个上游来源执行 allow_fork 与 license_code 检查。所有来源均满足才允许继续衍生，等价于多父 Merge 的权利交集；不能以某一父来源的宽松授权抵消另一父来源的限制。
- Fork、Collide confirm、Evolve confirm 均在创建关系前检查 custom 授权确认；确认信息冻结在每条 ForkRelation.license_snapshot 中，包含 acknowledged、acknowledged_by、acknowledged_at。未确认时返回 HTTP 422 / CUSTOM_LICENSE_CONFIRMATION_REQUIRED。
- publish_idea() 在作者设置 allow_fork=true 时重新核对完整祖先链；任何上游不允许衍生或授权类型不兼容时返回 HTTP 422 / INHERITED_LICENSE_BLOCKS_DERIVATION。
- 当前 Idea 的自有 license 作为 rights_chain 的最后一项加入后续计算；它不能覆盖更早祖先的许可限制。授权快照和关系记录不因来源撤回而删除。
- 回归测试覆盖多代 custom 快照传播、custom 未确认拒绝、Collide/Evolve 显式确认、多父任一来源受限拒绝，以及发布不能扩大祖先授权。
- 该实现不新增数据库列或 migration；授权链保存在既有 ForkRelation JSON metadata 中。
- exact-head CI 运行 [45023866140](https://github.com/nihcya/ideas/actions/runs/45023866140) 包含新增回归测试；在四个 job 全部完成前不记录全绿。生产 migrations 001/002/003 未执行。
