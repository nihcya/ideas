import 'package:flutter/material.dart';

/// 圆圈渲染数据：传递给 [CirclePainter] 的低层数据。
///
/// 由 [CircleCanvas] 根据 [CircleData] + 浮动偏移 + 状态计算后生成。
class CircleRenderData {
  /// 圆心坐标（已包含浮动偏移）。
  final Offset center;

  /// 圆圈半径（pt）。
  final double radius;

  /// 颜色 hex 字符串，格式 `#RRGGBB`。
  final String colorHex;

  /// 边框样式：`'gold-thin'` / `'none'` / `null`（主页）。
  final String? borderStyle;

  /// 不透明度（0-1），用于 fading 圆圈淡出 + 入场动画。
  final double opacity;

  /// 缩放比例（0-1+），用于入场动画（easeOutBack 可能略 >1）。
  final double scale;

  const CircleRenderData({
    required this.center,
    required this.radius,
    required this.colorHex,
    this.borderStyle,
    this.opacity = 1.0,
    this.scale = 1.0,
  });

  /// 将 colorHex 解析为 [Color]，格式为 `#RRGGBB`。
  Color get color => Color(int.parse('0xFF${colorHex.substring(1)}'));
}

/// 圆圈绘制器：在 [CustomPaint] 中渲染所有圆圈。
///
/// 遵循 TECH_CONSTRAINTS 1.1：
/// - 金边圆圈：先填充实心圆，再 stroke 边框（strokeWidth=3, Color(0xFFFFD700)）
/// - 无边框圆圈：只画实心圆
/// - 轻微阴影/辉光效果（MaskFilter.blur）
class CirclePainter extends CustomPainter {
  final List<CircleRenderData> circles;

  const CirclePainter({required this.circles});

  @override
  void paint(Canvas canvas, Size size) {
    for (final c in circles) {
      final baseColor = c.color;
      // 应用入场动画缩放（fading 状态也会缩小，二者叠加）
      final effectiveRadius = c.radius * c.scale;

      // 辉光：外侧模糊光晕（半径 8 + alpha 0.4，暗背景上更明显）
      final glowPaint = Paint()
        ..color = baseColor.withOpacity(c.opacity * 0.4)
        ..maskFilter = const MaskFilter.blur(BlurStyle.outer, 8);
      canvas.drawCircle(c.center, effectiveRadius, glowPaint);

      // 实心填充
      final fillPaint = Paint()..color = baseColor.withOpacity(c.opacity);
      canvas.drawCircle(c.center, effectiveRadius, fillPaint);

      // 金边圆圈：在填充之上绘制 stroke 边框
      if (c.borderStyle == 'gold-thin') {
        final borderPaint = Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 3
          ..color = const Color(0xFFFFD700).withOpacity(c.opacity);
        canvas.drawCircle(c.center, effectiveRadius, borderPaint);
      }
    }
  }

  @override
  bool shouldRepaint(covariant CirclePainter oldDelegate) {
    if (circles.length != oldDelegate.circles.length) return true;
    for (int i = 0; i < circles.length; i++) {
      final a = circles[i];
      final b = oldDelegate.circles[i];
      if (a.center != b.center ||
          a.radius != b.radius ||
          a.colorHex != b.colorHex ||
          a.borderStyle != b.borderStyle ||
          a.opacity != b.opacity ||
          a.scale != b.scale) {
        return true;
      }
    }
    return false;
  }
}
