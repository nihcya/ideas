# 点子 App UI 优化实施计划

> **计划制定日期**: 2026-07-28
> **基于**: PRD (TREA_CONTEXT.md) + 5 个 UI 优化方向 + Phase 1 代码库深度探索
> **执行原则**: 先 Git 备份 → 分阶段实施 → 每阶段独立可验证 → 单阶段失败不影响整体回滚

---

## 一、Summary（总览）

本计划基于对项目 9 个核心文件的深度探索，识别出 **3 个紧急 bug** + **5 个优化方向**，分 6 个阶段实施。每阶段独立 commit，便于精准回滚。

### 关键发现（来自 Phase 1 探索）

| 类型 | 问题 | 位置 | 严重度 |
|------|------|------|--------|
| Bug | 谱系图中心节点未传 `currentNode`，永远是金边"当前"占位 | `idea_detail_screen.dart#L644-647` | 🔴 高 |
| Bug | 双重 HapticFeedback 震动（CircleCanvas + ExploreScreen 各触发一次） | `explore_screen.dart#L45` + `circle_canvas.dart#L216` | 🟡 中 |
| Bug | 金边圆圈功能失效：前端 `CircleData.borderStyle` 后端 schema 根本没有此字段 | `models/idea.dart#L8-65` + `schemas/idea.py#L32-46` | 🟡 中 |
| 优化 | 谱系图无法支持多父节点（碰撞产生的双父），当前手写 Bezier 只支持线性 2 层 | `lineage_tree.dart` | 🔴 高 |
| 优化 | 圆圈画布只有 ±5px 浮动，无入场动画、无悬停反馈、无淡出过渡 | `circle_canvas.dart` | 🟡 中 |
| 优化 | 演化菜单是底部弹窗，不符合"在点子周围环形选择"的直觉 | `evolve_menu.dart` | 🟢 低 |
| 优化 | 今日一点页倒计时无圆环动画，氛围感不足 | `spark_screen.dart` | 🟢 低 |
| 优化 | 主题系统形同虚设，11 处硬编码 `Color(0xFF1A1A1E)`，7 处硬编码金色 | 全项目 | 🟡 中 |

---

## 二、Current State Analysis（现状分析）

### 2.1 项目结构

```
frontend/lib/
├── theme/app_theme.dart              # 主题（颜色变量化但未应用）
├── widgets/
│   ├── circle_canvas.dart            # 主页圆圈画布（增量布局 + ±5px 浮动）
│   ├── circle_painter.dart           # 圆圈绘制（辉光+填充+金边 三层）
│   ├── lineage_tree.dart             # 谱系图（Stack + Bezier，2 层）
│   └── evolve_menu.dart              # 演化菜单（底部弹窗 + 漫步动效）
├── screens/
│   ├── explore_screen.dart           # 主页（CircleCanvas + FAB）
│   ├── idea_detail_screen.dart       # 详情页（大圆圈 + 谱系图 + 操作栏）
│   └── spark_screen.dart             # 今日一点（倒计时 + TextField）
└── models/idea.dart                  # 数据模型（与后端 schema 部分不一致）
```

### 2.2 关键约束（来自 project_memory.md）

- **谱系图渲染禁止使用 graphview 库**（2026-07-28 事故：LateInitializationError）
- 前端 API 默认 `http://127.0.0.1:8765/api`
- 前端构建必须 `flutter build web --release`
- 引入新依赖前必须 PoC，核心 UI 组件替换需保留可回退路径

### 2.3 后端 API 返回的可用字段

- `IdeaDetail.source`（ugc/pgc/today_spark/fork/merge/evolve）— 前端未使用
- `IdeaDetail.is_forkable` — 前端未使用，但 Fork 按钮始终可点
- `LineageNode` 仅有 `id/color_hex/author/title`，无 `fork_count/created_at`

---

## 三、Proposed Changes（分阶段实施方案）

### 阶段 0：Git 备份（实施前必做）

**目的**: 建立回滚锚点，单阶段失败可精准回退。

**操作**:
```powershell
cd f:\treaFiles\Ideas\ideas\idea-app
git add -A
git status  # 人工确认无敏感文件（.env 等）
git commit -m "chore: snapshot before UI optimization (5 directions + 3 bug fixes)"
git tag pre-ui-optimization
```

**验证**: `git log -1 --oneline` 显示新 commit；`git tag` 列表包含 `pre-ui-optimization`。

---

### 阶段 1：紧急 Bug 修复（P0）

**目的**: 修复 3 个影响功能的 bug，改动最小、风险最低、立即可验证。

#### 1.1 修复谱系图中心节点不显示当前 idea

**文件**: `frontend/lib/screens/idea_detail_screen.dart`

**改动位置**: L644-647（`LineageTree` 调用处）

**当前代码**:
```dart
LineageTree(
  lineage: detail.lineage,
  onTap: onCircleTap,
)
```

**改为**:
```dart
LineageTree(
  lineage: detail.lineage,
  currentNode: LineageNode(
    id: detail.id,
    colorHex: detail.colorHex,
    author: detail.author.username,
    title: detail.content.length > 30
        ? '${detail.content.substring(0, 30)}…'
        : detail.content,
  ),
  onTap: onCircleTap,
)
```

**为什么**: `LineageTree` 已经支持 `currentNode` 参数（[lineage_tree.dart#L19-25](file:///f:/treaFiles/Ideas/ideas/idea-app/frontend/lib/widgets/lineage_tree.dart)），但详情页从未传入。修复后中心节点会显示当前 idea 的真实颜色+作者+标题，而非金边占位。

#### 1.2 删除双重震动反馈

**文件**: `frontend/lib/screens/explore_screen.dart`

**改动位置**: L44-47

**当前代码**:
```dart
void _onCircleTap(String id) {
  HapticFeedback.selectionClick();  // ← 删除此行
  context.push('/idea/$id');
}
```

**改为**:
```dart
void _onCircleTap(String id) {
  context.push('/idea/$id');
}
```

**为什么**: `circle_canvas.dart#L216` 已在命中测试中触发 `HapticFeedback.selectionClick()`，外层再触发一次会造成双重震动，体验割裂。

#### 1.3 修复金边圆圈功能（前端清理 + 后端补字段）

**前端文件**: `frontend/lib/models/idea.dart`

**改动**: 在 `CircleData` 的 `fromJson` 中将 `borderStyle` 改为可选解析，若后端不返回则根据 `isOwn` 推断：
```dart
borderStyle: json['border_style'] ?? (json['is_own'] == true ? 'gold-thin' : null),
```

**后端文件**: `backend/schemas/idea.py`

**改动**: 在 `CircleData` schema 中新增 `border_style: str | None = None` 字段；在 `backend/routers/ideas.py#L49-138` 的 explore 接口中，根据 `is_own` 字段填充 `border_style`：
```python
border_style='gold-thin' if idea.author_id == current_user_id else None
```

**为什么**: 当前前端 `CircleData.borderStyle` 永远是 null（后端不返回），导致 `CirclePainter` 的金边逻辑形同虚设。后端补字段更合理，前端只做渲染。

**验证**:
- 启动前后端，登录后查看主页：自己产生的点子应显示金边，收集的不显示
- 谱系图中心节点应显示当前 idea 真实信息
- 点击圆圈只触发一次震动

---

### 阶段 2：圆圈画布动效升级（方向 1，P0）

**目的**: 提升首页第一印象，增加入场动画、悬停反馈、淡出过渡。

**文件**: `frontend/lib/widgets/circle_canvas.dart` + `frontend/lib/widgets/circle_painter.dart`

#### 2.1 新增圆圈入场动画

**改动**: 在 `_LayoutCircle` 中新增 `addedAt: DateTime`，在 `_buildRenderData` 中根据 `DateTime.now().difference(addedAt)` 计算 scale 和 opacity：

```dart
// 新增入场动画控制器（_CircleCanvasState）
late final AnimationController _enterController;

// initState
_enterController = AnimationController(
  duration: const Duration(milliseconds: 600),
  vsync: this,
)..forward();

// _buildRenderData 中
final elapsed = DateTime.now().difference(c.addedAt);
final t = (elapsed.inMilliseconds / 600).clamp(0.0, 1.0);
final enterCurve = Curves.easeOutBack.transform(t);
// 应用 scale: enterCurve, opacity: t
```

**实现细节**: 用 `Curves.easeOutBack` 让圆圈"弹"出来，600ms 内完成。

#### 2.2 修复命中测试反向遍历

**改动位置**: `circle_canvas.dart#L200-221`

**当前**: 正向遍历，第一个匹配就返回，导致上层圆圈点不到。

**改为**: 反向遍历（`for (final c in _layoutMap.values.toList().reversed)`），让后绘制（视觉上层）的圆圈优先命中。

#### 2.3 优化 CirclePainter 辉光效果

**文件**: `circle_painter.dart#L46-68`

**改动**:
- 辉光 `MaskFilter.blur(BlurStyle.outer, 4)` → `BlurStyle.outer, 8`（增大模糊半径）
- 辉光 alpha 从 `0.25` → `0.4`（提高可见度）
- 把 `Paint` 缓存为成员变量，按 colorHex 分组（避免每帧 new Paint）

#### 2.4 修复旋转屏 X 坐标溢出

**改动位置**: `circle_canvas.dart#L78-87`（`didUpdateWidget`）

**新增**: 在 `didUpdateWidget` 中检测 `MediaQuery.sizeOf(context).width` 变化，若变化超过阈值则清空 `_layoutMap` 强制重新布局。

**验证**:
- 重启前端，圆圈出现时有"弹出"动效
- 圆圈重叠时点击上层圆圈能正确命中
- 暗背景上辉光更明显
- 旋转屏幕后圆圈不溢出屏幕

---

### 阶段 3：力导向谱系图（方向 2，P0，纯 Dart 实现）

**目的**: 替代当前手写 Bezier 2 层布局，支持多父节点（碰撞场景），不引入 graphview。

**策略**: **直接抄源码**，不添加 pub 依赖（遵循 project_memory.md 硬约束）。

**参考**: [MathGaps/d3-force-flutter](https://github.com/MathGaps/d3-force-flutter) 的 velocity Verlet 积分实现。

#### 3.1 新增力导向布局文件

**新文件**: `frontend/lib/widgets/force_layout.dart`

**内容**: 移植 d3-force 的核心物理模拟：
- `Node` 类：position, velocity, fixed
- `Link` 类：source, target, distance
- `Force` 接口：apply(nodes, links, alpha)
- 实现 3 种力：
  - `ChargeForce`：节点间斥力（防止重叠）
  - `LinkForce`：连接节点间的弹簧力（保持距离）
  - `CenterForce`：向中心收敛（防止漂移）
- `Simulation` 类：tick() 推进一帧，alpha 衰减

**预估代码量**: ~300 行（纯 Dart，无依赖）

#### 3.2 重写 LineageTree

**文件**: `frontend/lib/widgets/lineage_tree.dart`

**新实现**:
```dart
class LineageTree extends StatefulWidget {
  final Lineage lineage;
  final LineageNode? currentNode;
  final void Function(String ideaId) onTap;
  // ...
}

class _LineageTreeState extends State<LineageTree>
    with SingleTickerProviderStateMixin {
  late final Simulation _simulation;
  late final Ticker _ticker;

  @override
  void initState() {
    super.initState();
    _buildGraph();
    _ticker = Ticker(_onTick);
    _ticker.start();
  }

  void _buildGraph() {
    // 1. 添加所有节点（parents + current + children）
    // 2. 添加边（parent → current, current → child）
    // 3. 初始化位置（圆形排列在中心周围）
    // 4. 固定当前节点在中心
  }

  void _onTick(Duration elapsed) {
    _simulation.tick();
    if (_simulation.isStable()) _ticker.stop();
    setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    return InteractiveViewer(
      minScale: 0.5,
      maxScale: 2.0,
      child: SizedBox(
        width: 400,
        height: 400,
        child: CustomPaint(
          painter: ForceGraphPainter(
            nodes: _simulation.nodes,
            links: _simulation.links,
            currentNode: widget.currentNode,
            onTap: widget.onTap,
          ),
          size: const Size(400, 400),
        ),
      ),
    );
  }
}
```

**ForceGraphPainter**: 绘制节点（圆+作者+标题）、连接线（带渐变）、当前节点金边。

#### 3.3 保留旧实现作为 fallback

**重命名**: `lineage_tree.dart` → `lineage_tree_legacy.dart`（保留旧 Stack+Bezier 实现）

**目的**: 若力导向布局出现问题，可快速切换回旧实现。

**验证**:
- 详情页谱系图：节点自然散开，无重叠
- 碰撞产生的双父节点：两个父节点都能正确连接到当前节点
- 缩放/拖拽：InteractiveViewer 工作正常
- 性能：60fps（单帧 < 16ms）

---

### 阶段 4：径向演化菜单（方向 3，P1）

**目的**: 把演化菜单从底部弹窗改为点子周围的环形选择，更符合"在点子上长按弹出"的直觉。

**文件**: `frontend/lib/widgets/evolve_menu.dart` + `frontend/lib/screens/idea_detail_screen.dart`

#### 4.1 新增 RadialMenu widget

**新文件**: `frontend/lib/widgets/radial_menu.dart`

**参考**: [rasitayaz/flutter-pie-menu](https://github.com/rasitayaz/flutter-pie-menu) 的实现思路（不引入依赖，直接抄源码）。

**实现**:
```dart
class RadialMenu extends StatefulWidget {
  final Offset center;           // 中心点（点子圆圈中心）
  final double radius;           // 环形半径
  final List<RadialMenuItem> items;
  final VoidCallback? onCancel;
}

class RadialMenuItem {
  final String label;
  final IconData icon;
  final Color color;
  final VoidCallback onTap;
}
```

- 用 `Overlay` + `OverlayEntry` 全屏覆盖
- 用 `AnimatedBuilder` + `AnimationController` 控制扇形展开动画
- 用 `CustomPainter` 绘制扇形背景 + 连接线
- 用 `GestureDetector` 检测点击落点

#### 4.2 改造详情页触发方式

**文件**: `idea_detail_screen.dart`

**改动**: 底部"演化"按钮点击时，不再调 `showEvolveMenu`，而是：
1. 计算大圆圈在屏幕中的中心坐标
2. 用 `OverlayEntry` 显示 RadialMenu
3. 用户选择"碰撞"或"演化"后，菜单消失，进入对应流程

**保留**: `evolve_menu.dart` 旧实现作为 fallback（重命名为 `evolve_menu_legacy.dart`）。

**验证**:
- 点击"演化"按钮：圆圈周围弹出环形菜单
- 选择"碰撞"：菜单消失，进入碰撞流程
- 点击空白处：菜单消失，不触发任何操作
- 震动反馈：选择时触发 `HapticFeedback.mediumImpact()`

---

### 阶段 5：今日一点动效（方向 4，P2）

**目的**: 提升倒计时氛围感，增加题目展示动效。

**文件**: `frontend/lib/screens/spark_screen.dart`

#### 5.1 倒计时圆环动画

**改动**: 在倒计时 Row 中，把 `Icons.timer_outlined` 替换为 `CustomPaint` 绘制圆环：
```dart
SizedBox(
  width: 32, height: 32,
  child: CustomPaint(
    painter: CountdownRingPainter(
      progress: _remaining / widget.durationSeconds,  // 0-1
      color: _remaining <= 30 ? Color(0xFFFF5252) : Color(0xFFFFD700),
    ),
  ),
)
```

**新文件**: `frontend/lib/widgets/countdown_ring_painter.dart`（~50 行）

#### 5.2 题目渐显动效

**改动**: 标题 Text 外包一层 `AnimatedSwitcher` + `FadeTransition`，数据加载完成时渐显：
```dart
AnimatedSwitcher(
  duration: const Duration(milliseconds: 600),
  child: Text(data.question, key: ValueKey(data.question), ...),
)
```

#### 5.3 修复草稿回填

**改动位置**: `spark_screen.dart#L19`

**当前**: `final _ctrl = TextEditingController();` 永远是空。

**改为**: 在 `_initFromData` 中：
```dart
if (data.hasDraft && data.draftContent != null) {
  _ctrl.text = data.draftContent!;
}
```

**验证**:
- 倒计时圆环随时间递减，最后 30 秒变红
- 题目加载完成时有渐显效果
- 有草稿时进入页面，草稿内容自动回填到输入框

---

### 阶段 6：主题系统重构（方向 5，P2）

**目的**: 消除硬编码颜色，统一主题管理，为后续 lightTheme 支持打基础。

**文件**: `frontend/lib/theme/app_theme.dart` + 全项目硬编码颜色清理

#### 6.1 扩展主题定义

**文件**: `app_theme.dart`

**新增**:
```dart
class AppColors extends ThemeExtension<AppColors> {
  final Color surfaceVariant;   // 0xFF1A1A1E
  final Color cardHover;        // 0xFF2A2A2E
  final Color goldGlow;         // 0xFFFFD700 with alpha
  // ...
}
```

**新增 ThemeData**:
- `bottomSheetTheme`: 圆角 16 + 背景 `_surface`
- `dialogTheme`: 背景 `_surface` + 圆角 12
- `snackBarTheme`: 背景 `_card` + 字色 `_textPrimary`
- `floatingActionButtonTheme`: 金底黑字
- `dividerTheme`: color `_dividerColor`, thickness 1

#### 6.2 替换硬编码颜色

**批量替换**（用 Grep 定位 + Edit 替换）:

| 原值 | 替换为 | 涉及文件 |
|------|--------|----------|
| `Color(0xFF1A1A1E)` | `Theme.of(context).colorScheme.surface` | idea_detail_screen, evolve_menu, spark_screen 等 |
| `Color(0xFFFFD700)` | `Theme.of(context).colorScheme.primary` | explore_screen, idea_detail_screen, circle_painter 等 |
| `Color(0xFF9A9AA0)` | `Theme.of(context).colorScheme.onSurfaceVariant` | idea_detail_screen, lineage_tree 等 |
| `Color(0xFF242428)` | `Theme.of(context).cardColor` | 各处 |
| `Color(0xFF2A2A2E)` | `Theme.of(context).dividerColor` | idea_detail_screen Divider |
| `Color(0xFFF5F5F7)` | `Theme.of(context).colorScheme.onSurface` | lineage_tree, idea_detail_screen |

**注意**: `circle_painter.dart` 和 `circle_canvas.dart` 中的颜色是动态数据色（来自 idea.colorHex），不替换；只替换 UI 框架色。

**验证**:
- `grep -rn "Color(0xFF" frontend/lib/screens frontend/lib/widgets` 输出大幅减少
- 应用界面无明显视觉变化（颜色值不变，只是来源变了）
- 后续若要支持 lightTheme，只需修改 `app_theme.dart` 一处

---

## 四、Assumptions & Decisions（假设与决策）

### 4.1 关键决策

1. **力导向布局不引入依赖，直接抄源码** — 遵循 project_memory.md 硬约束，避免重蹈 graphview 翻车覆辙。
2. **保留旧实现作为 fallback** — `lineage_tree.dart` → `lineage_tree_legacy.dart`，`evolve_menu.dart` → `evolve_menu_legacy.dart`，单阶段失败可快速切换。
3. **后端补 `border_style` 字段** — 而非前端臆造，保证数据真实性。
4. **不引入 freezed / equatable** — 虽然探索发现 `shouldRepaint` 失效问题，但引入新依赖风险高，且当前性能未到瓶颈，留待后续。
5. **不修复"碰撞/演化流程冗长 4 步 modal"** — 这是产品流程问题，非 UI 优化范畴，需产品决策后再改。
6. **lightTheme 不做完善** — 当前所有页面都用暗色，完善 lightTheme 工作量大且无用户需求，仅清理死代码引用。

### 4.2 假设

- 后端 venv 已存在且可用（`backend/venv/Scripts/python.exe`）
- 前端依赖已拉取（`flutter pub get` 已执行）
- 当前工作区干净（阶段 0 会先 commit）
- 后端 `IdeaDetail.author` 是 dict 但包含 `username` 字段（探索确认）

### 4.3 不做的事（Out of Scope）

- 不引入任何新的 pub 依赖
- 不修改碰撞/演化的业务流程
- 不做 lightTheme 完善
- 不做国际化（i18n）
- 不做搜索功能
- 不做骨架屏（留待后续）

---

## 五、Verification Steps（验证步骤）

### 5.1 每阶段通用验证

```powershell
# 1. 编译检查
cd f:\treaFiles\Ideas\ideas\idea-app\frontend
flutter analyze  # 应无 error

# 2. 构建检查
flutter build web --release  # 应成功

# 3. 重启前端验证
cd build\web; python -m http.server 8003
```

### 5.2 阶段性功能验证

| 阶段 | 验证点 | 期望结果 |
|------|--------|----------|
| 1 | 详情页谱系图中心节点 | 显示当前 idea 真实颜色+作者+标题 |
| 1 | 点击圆圈震动 | 只震动一次 |
| 1 | 自己产生的点子金边 | 显示金边 |
| 2 | 首页圆圈入场 | 600ms 弹出动效 |
| 2 | 圆圈重叠点击 | 命中上层圆圈 |
| 3 | 谱系图布局 | 节点自然散开，无重叠 |
| 3 | 碰撞产生的双父节点 | 两父节点都连接到当前 |
| 4 | 点击"演化"按钮 | 圆圈周围弹出环形菜单 |
| 5 | 倒计时圆环 | 随时间递减，30s 变红 |
| 5 | 草稿回填 | 有草稿时自动填充 |
| 6 | 硬编码颜色 | grep 输出大幅减少 |

### 5.3 最终回归测试

- 所有页面无白屏、无 LateInitializationError
- 主页 → 详情 → 碰撞/演化 → 新详情 完整流程跑通
- 前后端联调正常（API 调用、数据渲染）
- `git log --oneline` 应有 6+ 个新 commit（每阶段一个）

---

## 六、Rollback Plan（回滚方案）

### 6.1 单阶段回滚

```powershell
git revert <commit-hash>
```

### 6.2 整体回滚到优化前

```powershell
git reset --hard pre-ui-optimization
```

### 6.3 力导向谱系图失败时的快速切换

若阶段 3 力导向布局出现性能问题或渲染异常：
```dart
// idea_detail_screen.dart 中临时切换
import 'lineage_tree_legacy.dart';  // 替代 lineage_tree.dart
```

---

## 七、实施顺序与依赖

```
阶段 0 (Git 备份)
  ↓
阶段 1 (Bug 修复) ← 独立，无依赖
  ↓
阶段 2 (圆圈动效) ← 独立，无依赖
  ↓
阶段 3 (力导向谱系图) ← 依赖阶段 1.1（中心节点修复）
  ↓
阶段 4 (径向菜单) ← 独立，无依赖
  ↓
阶段 5 (今日一点动效) ← 独立，无依赖
  ↓
阶段 6 (主题重构) ← 最后做，避免中途改色影响其他阶段验证
```

每阶段完成后：
1. `git add` + `git commit`（阶段独立 commit）
2. 启动前后端验证
3. 验证通过后进入下一阶段
4. 验证失败则 `git revert` 回滚该阶段

---

## 八、预估工作量

| 阶段 | 改动文件数 | 新增代码行 | 难度 | 备注 |
|------|-----------|-----------|------|------|
| 0 | 0 | 0 | 简单 | Git 操作 |
| 1 | 4 | ~30 | 简单 | Bug 修复 |
| 2 | 2 | ~80 | 中等 | 动效 + 命中测试 |
| 3 | 2 新增 + 1 改造 | ~400 | 困难 | 力导向算法移植 |
| 4 | 1 新增 + 1 改造 | ~250 | 中等 | Overlay + 自定义绘制 |
| 5 | 1 改造 + 1 新增 | ~80 | 简单 | 圆环 + 渐显 |
| 6 | 1 改造 + 6+ 批量替换 | ~50 | 简单 | 主题扩展 + 替换 |

**总计**: ~890 行新代码，6 个 commit，覆盖 5 个优化方向 + 3 个 bug 修复。
