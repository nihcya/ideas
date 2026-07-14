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

  /// 不透明度（0-1），用于 fading 圆圈淡出。
  final double opacity;

  const CircleRenderData({
    required this.center,
    required this.radius,
    required this.colorHex,
    this.borderStyle,
    this.opacity = 1.0,
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

      // 轻微辉光/阴影：在圆圈外侧绘制模糊光晕，暗色背景上更突出
      final glowPaint = Paint()
        ..color = baseColor.withOpacity(c.opacity * 0.25)
        ..maskFilter = const MaskFilter.blur(BlurStyle.outer, 4);
      canvas.drawCircle(c.center, c.radius, glowPaint);

      // 实心填充
      final fillPaint = Paint()..color = baseColor.withOpacity(c.opacity);
      canvas.drawCircle(c.center, c.radius, fillPaint);

      // 金边圆圈：在填充之上绘制 stroke 边框
      if (c.borderStyle == 'gold-thin') {
        final borderPaint = Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 3
          ..color = const Color(0xFFFFD700).withOpacity(c.opacity);
        canvas.drawCircle(c.center, c.radius, borderPaint);
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
          a.opacity != b.opacity) {
        return true;
      }
    }
    return false;
  }
}
