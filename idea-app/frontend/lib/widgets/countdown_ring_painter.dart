import 'dart:math' as math;

import 'package:flutter/material.dart';

/// 倒计时圆环绘制器。
///
/// 绘制一个环形进度条：
/// - 背景圆环（暗色半透明）
/// - 前景圆弧（从顶部顺时针，随倒计时递减）
/// - 剩余 ≤ 30 秒时圆弧变红，否则金色
class CountdownRingPainter extends CustomPainter {
  /// 进度值 0-1（1=满，0=空）。
  final double progress;

  /// 圆弧颜色。
  final Color color;

  /// 背景圆环颜色。
  final Color backgroundColor;

  /// 圆环线宽。
  final double strokeWidth;

  const CountdownRingPainter({
    required this.progress,
    required this.color,
    this.backgroundColor = const Color(0x33FFFFFF),
    this.strokeWidth = 3.0,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = (math.min(size.width, size.height) - strokeWidth) / 2;

    // 1. 背景圆环
    final bgPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..color = backgroundColor;
    canvas.drawCircle(center, radius, bgPaint);

    // 2. 前景圆弧（从顶部 -π/2 开始，顺时针）
    final arcPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..color = color
      ..strokeCap = StrokeCap.round;

    final sweepAngle = progress * 2 * math.pi;
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      -math.pi / 2, // 从顶部开始
      sweepAngle, // 顺时针
      false,
      arcPaint,
    );
  }

  @override
  bool shouldRepaint(covariant CountdownRingPainter oldDelegate) {
    return progress != oldDelegate.progress || color != oldDelegate.color;
  }
}
