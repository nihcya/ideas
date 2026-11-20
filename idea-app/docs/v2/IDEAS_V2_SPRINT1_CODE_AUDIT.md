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
