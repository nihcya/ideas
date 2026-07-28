import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';
import 'package:flutter/services.dart';

import '../models/idea.dart';
import '../theme/app_theme.dart';
import 'force_layout.dart';

/// 谱系图（力导向布局版本）。
///
/// 使用纯 Dart 实现的力导向算法（force_layout.dart）替代旧版 Stack+Bezier 布局。
/// 优势：
/// - 支持多父节点（碰撞产生的双父场景）
/// - 节点自动散开，无重叠
/// - InteractiveViewer 支持缩放/拖拽
///
/// 旧版实现保留在 lineage_tree_legacy.dart 作为 fallback。
class LineageTree extends StatefulWidget {
  final Lineage lineage;

  /// 当前节点数据（谱系图的中心节点）。
  /// 为 null 时显示金边"当前"占位节点。
  final LineageNode? currentNode;

  /// 点击节点回调，参数为 ideaId。
  final void Function(String ideaId) onTap;

  const LineageTree({
    super.key,
    required this.lineage,
    required this.onTap,
    this.currentNode,
  });

  @override
  State<LineageTree> createState() => _LineageTreeState();
}

class _LineageTreeState extends State<LineageTree>
    with SingleTickerProviderStateMixin {
  static const double _canvasSize = 400.0;
  static const double _nodeRadius = 22.0;
  static const double _currentNodeRadius = 28.0;
  static const Offset _center = Offset(_canvasSize / 2, _canvasSize / 2);

  late final ForceSimulation _simulation;
  late final Ticker _ticker;

  /// 当前被拖拽的节点（null 表示无拖拽）。
  ForceNode? _draggingNode;

  @override
  void initState() {
    super.initState();
    _buildSimulation();
    _ticker = Ticker(_onTick);
    _ticker.start();
  }

  @override
  void didUpdateWidget(covariant LineageTree oldWidget) {
    super.didUpdateWidget(oldWidget);
    // lineage 变化时重建模拟
    if (widget.lineage != oldWidget.lineage ||
        widget.currentNode != oldWidget.currentNode) {
      _buildSimulation();
      _ticker.start();
    }
  }

  @override
  void dispose() {
    _ticker.dispose();
    super.dispose();
  }

  void _buildSimulation() {
    final nodes = <ForceNode>[];
    final links = <ForceLink>[];
    final nodeByKey = <String, ForceNode>{};

    // 1. 当前节点（固定在中心）
    final currentNode = widget.currentNode;
    final currentKey = currentNode?.id ?? '__current__';
    final currentData = currentNode ??
        LineageNode(
          id: currentKey,
          colorHex: '#FFD700',
          author: '',
          title: '当前',
        );
    final currentNodeForce = ForceNode(
      key: currentKey,
      data: {
        'node': currentData,
        'isCurrent': true,
      },
      position: _center,
      fixed: true,
      radius: _currentNodeRadius,
    );
    nodes.add(currentNodeForce);
    nodeByKey[currentKey] = currentNodeForce;

    // 2. 父节点（圆形排列在上方）
    final parents = widget.lineage.parents;
    for (int i = 0; i < parents.length; i++) {
      final p = parents[i];
      final angle = -math.pi / 2 + (i - (parents.length - 1) / 2) * 0.6;
      final initialPos = _center +
          Offset(
            math.cos(angle) * 120,
            math.sin(angle) * 120,
          );
      final node = ForceNode(
        key: p.id,
        data: {'node': p, 'isCurrent': false},
        position: initialPos,
        radius: _nodeRadius,
      );
      nodes.add(node);
      nodeByKey[p.id] = node;
      // 父 → 当前
      links.add(ForceLink(
        source: node,
        target: currentNodeForce,
        distance: 100,
      ));
    }

    // 3. 子节点（圆形排列在下方）
    final children = widget.lineage.children;
    final childCount = children.length;
    for (int i = 0; i < childCount; i++) {
      final c = children[i];
      final angle = math.pi / 2 +
          (i - (childCount - 1) / 2) * (0.8 / math.max(childCount, 1));
      final initialRadius = 120.0 + (i ~/ 5) * 60; // 超过 5 个时分层
      final initialPos = _center +
          Offset(
            math.cos(angle) * initialRadius,
            math.sin(angle) * initialRadius,
          );
      final node = ForceNode(
        key: c.id,
        data: {'node': c, 'isCurrent': false},
        position: initialPos,
        radius: _nodeRadius,
      );
      nodes.add(node);
      nodeByKey[c.id] = node;
      // 当前 → 子
      links.add(ForceLink(
        source: currentNodeForce,
        target: node,
        distance: 100,
      ));
    }

    _simulation = ForceSimulation(
      nodes: nodes,
      links: links,
      forces: [
        ChargeForce(strength: -600.0),
        LinkForce(strength: 0.4),
        CenterForce(center: _center),
        CollideForce(),
      ],
    );
  }

  void _onTick(Duration elapsed) {
    _simulation.tick();
    if (_simulation.isStable()) {
      _ticker.stop();
    }
    setState(() {});
  }

  /// 命中测试：返回点击位置对应的 ideaId（无命中返回 null）。
  String? _hitTest(Offset localPos) {
    // 反向遍历：后绘制的在上层
    for (final n in _simulation.nodes.reversed) {
      final dist = (localPos - n.position).distance;
      if (dist <= n.radius) {
        return n.key == '__current__' ? null : n.key;
      }
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    return InteractiveViewer(
      minScale: 0.5,
      maxScale: 2.5,
      boundaryMargin: const EdgeInsets.all(50),
      child: SizedBox(
        width: _canvasSize,
        height: _canvasSize,
        child: GestureDetector(
          onTapUp: (details) {
            final ideaId = _hitTest(details.localPosition);
            if (ideaId != null) {
              HapticFeedback.selectionClick();
              widget.onTap(ideaId);
            }
          },
          onPanStart: (details) {
            // 拖拽节点：命中则标记为 dragging
            final ideaId = _hitTest(details.localPosition);
            if (ideaId != null) {
              _draggingNode = _simulation.nodes.firstWhere(
                (n) => n.key == ideaId,
              );
              _simulation.reheat(0.5);
              _ticker.start();
            }
          },
          onPanUpdate: (details) {
            if (_draggingNode != null) {
              setState(() {
                _draggingNode!.position = details.localPosition;
              });
            }
          },
          onPanEnd: (_) {
            _draggingNode = null;
          },
          child: CustomPaint(
            painter: _ForceGraphPainter(
              nodes: _simulation.nodes,
              links: _simulation.links,
              colors: AppColors.of(context),
            ),
            size: const Size(_canvasSize, _canvasSize),
          ),
        ),
      ),
    );
  }
}

/// 力导向谱系图绘制器。
class _ForceGraphPainter extends CustomPainter {
  final List<ForceNode> nodes;
  final List<ForceLink> links;
  final AppColors colors;

  const _ForceGraphPainter({
    required this.nodes,
    required this.links,
    required this.colors,
  });

  @override
  void paint(Canvas canvas, Size size) {
    // 1. 绘制连接线（先画线再画节点，节点在上层）
    final linePaint = Paint()
      ..color = colors.lineageLine
      ..strokeWidth = 1.5
      ..style = PaintingStyle.stroke;

    for (final link in links) {
      final path = _bezierPath(link.source.position, link.target.position);
      canvas.drawPath(path, linePaint);
    }

    // 2. 绘制节点
    for (final node in nodes) {
      final data = node.data['node'] as LineageNode;
      final isCurrent = node.data['isCurrent'] as bool;
      final baseColor = data.color;
      final radius = node.radius;

      // 辉光
      final glowPaint = Paint()
        ..color = baseColor.withOpacity(isCurrent ? 0.5 : 0.3)
        ..maskFilter = const MaskFilter.blur(BlurStyle.outer, 6);
      canvas.drawCircle(node.position, radius, glowPaint);

      // 实心填充
      final fillPaint = Paint()..color = baseColor;
      canvas.drawCircle(node.position, radius, fillPaint);

      // 当前节点金边
      if (isCurrent) {
        final borderPaint = Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2.5
          ..color = colors.gold;
        canvas.drawCircle(node.position, radius, borderPaint);
      }

      // 作者名（节点下方）
      final author = data.author;
      if (author.isNotEmpty) {
        final authorSpan = TextSpan(
          text: author,
          style: TextStyle(
            color: colors.textSecondary,
            fontSize: 10,
          ),
        );
        final authorPainter = TextPainter(
          text: authorSpan,
          textDirection: TextDirection.ltr,
          textAlign: TextAlign.center,
        )..layout(maxWidth: 80);
        authorPainter.paint(
          canvas,
          Offset(
            node.position.dx - authorPainter.width / 2,
            node.position.dy + radius + 4,
          ),
        );
      }
    }
  }

  /// 绘制 S 形 Bezier 曲线连接两点。
  Path _bezierPath(Offset p1, Offset p2) {
    final midY = (p1.dy + p2.dy) / 2;
    final c1 = Offset(p1.dx, midY);
    final c2 = Offset(p2.dx, midY);
    return Path()
      ..moveTo(p1.dx, p1.dy)
      ..cubicTo(c1.dx, c1.dy, c2.dx, c2.dy, p2.dx, p2.dy);
  }

  @override
  bool shouldRepaint(covariant _ForceGraphPainter oldDelegate) {
    return nodes != oldDelegate.nodes ||
        links != oldDelegate.links ||
        colors != oldDelegate.colors;
  }
}
