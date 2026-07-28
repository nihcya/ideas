import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../models/idea.dart';
import '../theme/app_theme.dart';

/// 谱系图（点子详情页用）。
///
/// 2 层结构（3 行视觉布局）：
/// - 父节点（0-2个）在上
/// - 当前节点在中
/// - 子节点（最多10个）在下
///
/// 每个节点是一个小圆圈（直径 40pt），含作者名和点子前30字。
/// 节点间用 Bezier 曲线连接。点击节点跳转到对应点子详情。
class LineageTree extends StatelessWidget {
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

  /// 节点圆圈直径。
  static const double nodeDiameter = 40.0;

  /// 节点间距（水平）。
  static const double nodeSpacing = 64.0;

  /// 行间距（垂直）。
  static const double rowSpacing = 80.0;

  /// 节点下方文字区域高度。
  static const double labelHeight = 56.0;

  @override
  Widget build(BuildContext context) {
    final colors = AppColors.of(context);
    final parents = lineage.parents;
    final children = lineage.children;

    // 计算各行节点数
    final parentCount = parents.length;
    final childCount = children.length;

    // 计算宽度：取三行中最宽的
    final parentWidth = math.max(parentCount - 1, 0) * nodeSpacing + nodeDiameter;
    final childWidth = math.max(childCount - 1, 0) * nodeSpacing + nodeDiameter;
    final minWidth = nodeDiameter * 2; // 至少容纳当前节点
    final contentWidth = math.max(
      math.max(parentWidth, childWidth),
      minWidth,
    );

    // 计算高度：3 行节点 + 2 个行间距 + 标签
    final contentHeight =
        nodeDiameter * 3 + rowSpacing * 2 + labelHeight * 3;

    // 各行 Y 坐标（圆心）
    final parentY = nodeDiameter / 2;
    final currentY = parentY + nodeDiameter + rowSpacing + labelHeight;
    final childY = currentY + nodeDiameter + rowSpacing + labelHeight;

    // 各行 X 坐标（圆心）
    final parentXs = _computeRowXs(parentCount, contentWidth);
    final childXs = _computeRowXs(childCount, contentWidth);
    final currentX = contentWidth / 2;

    return Center(
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: SizedBox(
          width: contentWidth,
          height: contentHeight,
          child: Stack(
            clipBehavior: Clip.none,
            children: [
              // 连接线（CustomPainter）
              CustomPaint(
                size: Size(contentWidth, contentHeight),
                painter: _LineageLinePainter(
                  parents: parents,
                  parentXs: parentXs,
                  parentY: parentY,
                  currentX: currentX,
                  currentY: currentY,
                  children: children,
                  childXs: childXs,
                  childY: childY,
                  lineColor: colors.lineageLine,
                ),
              ),
              // 父节点
              for (int i = 0; i < parents.length; i++)
                _buildNode(
                  parents[i],
                  parentXs[i],
                  parentY,
                  isCurrent: false,
                  colors: colors,
                ),
              // 当前节点
              _buildCurrentNode(currentX, currentY, colors),
              // 子节点
              for (int i = 0; i < children.length; i++)
                _buildNode(
                  children[i],
                  childXs[i],
                  childY,
                  isCurrent: false,
                  colors: colors,
                ),
            ],
          ),
        ),
      ),
    );
  }

  /// 计算一行中各节点的 X 坐标（圆心），居中排列。
  List<double> _computeRowXs(int count, double totalWidth) {
    if (count == 0) return [];
    final startX = (totalWidth - (count - 1) * nodeSpacing - nodeDiameter) / 2;
    return List.generate(
      count,
      (i) => startX + i * nodeSpacing + nodeDiameter / 2,
    );
  }

  /// 当前节点：有数据时显示完整节点，无数据时显示金边占位。
  Widget _buildCurrentNode(double x, double y, AppColors colors) {
    if (currentNode != null) {
      return _buildNode(currentNode!, x, y, isCurrent: true, colors: colors);
    }
    return Positioned(
      left: x - nodeDiameter / 2,
      top: y - nodeDiameter / 2,
      child: SizedBox(
        width: nodeDiameter,
        height: nodeDiameter + labelHeight,
        child: Column(
          children: [
            Container(
              width: nodeDiameter,
              height: nodeDiameter,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: colors.gold,
                border: Border.all(
                  color: colors.gold,
                  width: 2.5,
                ),
                boxShadow: [
                  BoxShadow(
                    color: colors.gold.withValues(alpha: 0.4),
                    blurRadius: 8,
                    spreadRadius: 1,
                  ),
                ],
              ),
            ),
            const SizedBox(height: 4),
            Text(
              '当前',
              style: TextStyle(
                color: colors.gold,
                fontSize: 11,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildNode(LineageNode node, double x, double y,
      {required bool isCurrent, required AppColors colors}) {
    return Positioned(
      left: x - nodeDiameter / 2,
      top: y - nodeDiameter / 2,
      child: GestureDetector(
        onTap: () => onTap(node.id),
        child: SizedBox(
          width: nodeDiameter,
          height: nodeDiameter + labelHeight,
          child: Column(
            children: [
              Container(
                width: nodeDiameter,
                height: nodeDiameter,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: node.color,
                  border: isCurrent
                      ? Border.all(color: colors.gold, width: 2.5)
                      : null,
                  boxShadow: [
                    BoxShadow(
                      color: node.color.withValues(alpha: 0.35),
                      blurRadius: 6,
                      spreadRadius: 1,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 4),
              Text(
                node.author,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  color: colors.textPrimary,
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                _truncate(node.title, 30),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: colors.textSecondary,
                  fontSize: 10,
                  height: 1.2,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _truncate(String text, int max) {
    if (text.length <= max) return text;
    return '${text.substring(0, max)}…';
  }
}

/// 谱系图连接线绘制器：用 Bezier 曲线连接父→当前、当前→子。
class _LineageLinePainter extends CustomPainter {
  final List<LineageNode> parents;
  final List<double> parentXs;
  final double parentY;

  final double currentX;
  final double currentY;

  final List<LineageNode> children;
  final List<double> childXs;
  final double childY;

  final Color lineColor;

  _LineageLinePainter({
    required this.parents,
    required this.parentXs,
    required this.parentY,
    required this.currentX,
    required this.currentY,
    required this.children,
    required this.childXs,
    required this.childY,
    required this.lineColor,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.5
      ..color = lineColor;

    // 父节点 → 当前节点
    for (int i = 0; i < parents.length; i++) {
      final p1 = Offset(parentXs[i], parentY);
      final p2 = Offset(currentX, currentY);
      canvas.drawPath(_bezierPath(p1, p2), paint);
    }

    // 当前节点 → 子节点
    for (int i = 0; i < children.length; i++) {
      final p1 = Offset(currentX, currentY);
      final p2 = Offset(childXs[i], childY);
      canvas.drawPath(_bezierPath(p1, p2), paint);
    }
  }

  /// 三次 Bezier 曲线：起点和终点的控制点在垂直方向偏移。
  Path _bezierPath(Offset p1, Offset p2) {
    final midY = (p1.dy + p2.dy) / 2;
    final c1 = Offset(p1.dx, midY);
    final c2 = Offset(p2.dx, midY);
    return Path()
      ..moveTo(p1.dx, p1.dy)
      ..cubicTo(c1.dx, c1.dy, c2.dx, c2.dy, p2.dx, p2.dy);
  }

  @override
  bool shouldRepaint(covariant _LineageLinePainter oldDelegate) {
    return parents != oldDelegate.parents ||
        children != oldDelegate.children ||
        currentX != oldDelegate.currentX ||
        currentY != oldDelegate.currentY ||
        parentY != oldDelegate.parentY ||
        childY != oldDelegate.childY ||
        lineColor != oldDelegate.lineColor;
  }
}
