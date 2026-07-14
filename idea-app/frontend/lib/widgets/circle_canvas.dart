import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../models/idea.dart';
import 'circle_painter.dart';

/// 主页和仓库的圆圈画布。
///
/// 遵循 TECH_CONSTRAINTS 1.1 / 1.3 / 1.4：
/// - CustomPainter + CustomPaint 渲染（非 GridView/ListView）
/// - 真随机布局算法，避免重叠超过 30%
/// - 浮动动效（±5px，3秒周期，不同圆圈 delay 不同）
/// - 点击圆圈触发 HapticFeedback.selectionClick()
/// - 滚动加载：向下滚动时继续生成圆圈
/// - fading 圆圈变小变透明，faded 圆圈不显示
class CircleCanvas extends StatefulWidget {
  /// 圆圈数据列表（来自后端）。
  final List<CircleData> circles;

  /// 点击圆圈回调，参数为 ideaId。
  final void Function(String ideaId) onTap;

  /// 是否还有更多数据可加载。
  final bool hasMore;

  /// 滚动到底部时触发加载更多。
  final VoidCallback? onLoadMore;

  const CircleCanvas({
    super.key,
    required this.circles,
    required this.onTap,
    this.hasMore = false,
    this.onLoadMore,
  });

  @override
  State<CircleCanvas> createState() => _CircleCanvasState();
}

class _CircleCanvasState extends State<CircleCanvas>
    with TickerProviderStateMixin {
  /// 已布局圆圈的映射：ideaId -> _LayoutCircle
  final Map<String, _LayoutCircle> _layoutMap = {};

  /// 内容总高度（用于 SizedBox 撑开滚动区域）。
  double _contentHeight = 600;

  /// 浮动动效控制器（3秒周期，repeat + reverse）。
  late final AnimationController _floatController;

  /// 滚动控制器（用于检测滚动到底部）。
  late final ScrollController _scrollController;

  /// 是否正在加载更多（防重复触发）。
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _floatController = AnimationController(
      duration: const Duration(seconds: 3),
      vsync: this,
    )..repeat(reverse: true);
    _scrollController = ScrollController();
    _scrollController.addListener(_onScroll);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _updateLayout();
  }

  @override
  void didUpdateWidget(covariant CircleCanvas oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.circles != oldWidget.circles) {
      _isLoading = false;
      _updateLayout();
    }
    if (!widget.hasMore) {
      _isLoading = false;
    }
  }

  @override
  void dispose() {
    _floatController.dispose();
    _scrollController.removeListener(_onScroll);
    _scrollController.dispose();
    super.dispose();
  }

  /// 增量布局算法：
  /// - 新圆圈在已有内容下方寻找不重叠位置
  /// - 用 ideaId.hashCode 作为 Random 种子，保证确定性
  /// - 重叠判定：两圆心距离 > (r1 + r2) * 0.7 则不重叠
  void _updateLayout() {
    final width = MediaQuery.sizeOf(context).width;

    for (final d in widget.circles) {
      // 已存在则更新 data（forkCount/status 可能变化）
      final existing = _layoutMap[d.id];
      if (existing != null) {
        _layoutMap[d.id] = _LayoutCircle(
          center: existing.center,
          radius: existing.radius,
          data: d,
        );
        continue;
      }

      final radius = d.radius; // 30-60pt
      final random = math.Random(d.id.hashCode);

      // 在当前内容高度附近搜索位置（向上重叠 150pt，向下延伸 250pt）
      final searchTop = math.max(0.0, _contentHeight - 150);
      final searchBottom = _contentHeight + 250;

      Offset? pos;
      for (int attempt = 0; attempt < 60; attempt++) {
        final x = radius + random.nextDouble() * (width - 2 * radius);
        final y =
            searchTop + radius + random.nextDouble() * (searchBottom - searchTop - 2 * radius);
        final candidate = Offset(x, y);

        bool overlaps = false;
        for (final existing in _layoutMap.values) {
          final dist = (candidate - existing.center).distance;
          if (dist < (radius + existing.radius) * 0.7) {
            overlaps = true;
            break;
          }
        }
        if (!overlaps) {
          pos = candidate;
          break;
        }
      }

      // 找不到不重叠位置时，直接放在当前内容下方
      pos ??= Offset(
        radius + random.nextDouble() * (width - 2 * radius),
        _contentHeight + radius + 20,
      );

      _layoutMap[d.id] = _LayoutCircle(center: pos, radius: radius, data: d);
      _contentHeight = math.max(_contentHeight, pos.dy + radius + 30);
    }

    // 移除已不在列表中的圆圈
    final ids = widget.circles.map((c) => c.id).toSet();
    _layoutMap.removeWhere((id, _) => !ids.contains(id));
  }

  void _onScroll() {
    if (!_scrollController.hasClients) return;
    final pos = _scrollController.position;
    if (pos.pixels >= pos.maxScrollExtent - 300) {
      if (widget.hasMore && !_isLoading) {
        _isLoading = true;
        widget.onLoadMore?.call();
      }
    }
  }

  /// 构建渲染数据列表（应用浮动偏移 + 状态效果）。
  List<CircleRenderData> _buildRenderData(double t) {
    final result = <CircleRenderData>[];
    for (final c in _layoutMap.values) {
      // faded 圆圈不显示
      if (c.data.status == 'faded') continue;

      double opacity = 1.0;
      double radius = c.radius;
      if (c.data.status == 'fading') {
        opacity = 0.5;
        radius = c.radius * 0.7;
      }

      // 浮动偏移：±5px，不同圆圈 phase 不同（基于 id.hashCode）
      final phase = (c.data.id.hashCode.abs() % 360) * math.pi / 180.0;
      final yOffset = math.sin(t * math.pi * 2 + phase) * 5.0;

      result.add(CircleRenderData(
        center: Offset(c.center.dx, c.center.dy + yOffset),
        radius: radius,
        colorHex: c.data.colorHex,
        borderStyle: c.data.borderStyle,
        opacity: opacity,
      ));
    }
    return result;
  }

  /// 点击命中测试：找到点击位置对应的圆圈。
  void _handleTapUp(TapUpDetails details) {
    final localPos = details.localPosition;
    final t = _floatController.value;

    for (final c in _layoutMap.values) {
      if (c.data.status == 'faded') continue;

      double radius = c.radius;
      if (c.data.status == 'fading') radius = c.radius * 0.7;

      final phase = (c.data.id.hashCode.abs() % 360) * math.pi / 180.0;
      final yOffset = math.sin(t * math.pi * 2 + phase) * 5.0;
      final animatedCenter = Offset(c.center.dx, c.center.dy + yOffset);

      final dist = (localPos - animatedCenter).distance;
      if (dist <= radius) {
        HapticFeedback.selectionClick();
        widget.onTap(c.data.id);
        return;
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.sizeOf(context).width;

    return SingleChildScrollView(
      controller: _scrollController,
      child: SizedBox(
        width: width,
        height: _contentHeight,
        child: GestureDetector(
          onTapUp: _handleTapUp,
          behavior: HitTestBehavior.opaque,
          child: AnimatedBuilder(
            animation: _floatController,
            builder: (context, _) {
              return CustomPaint(
                painter: CirclePainter(
                  circles: _buildRenderData(_floatController.value),
                ),
                size: Size.infinite,
              );
            },
          ),
        ),
      ),
    );
  }
}

/// 内部布局圆圈数据：圆心 + 半径 + 原始 CircleData。
class _LayoutCircle {
  final Offset center;
  final double radius;
  final CircleData data;

  _LayoutCircle({
    required this.center,
    required this.radius,
    required this.data,
  });
}
