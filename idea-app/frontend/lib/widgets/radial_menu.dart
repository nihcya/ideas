import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// 径向菜单项。
class RadialMenuItem {
  final String label;
  final IconData icon;
  final Color color;
  final VoidCallback onTap;

  const RadialMenuItem({
    required this.label,
    required this.icon,
    required this.color,
    required this.onTap,
  });
}

/// 径向演化菜单：以大圆圈为中心，扇形按钮环形展开。
///
/// 使用 Overlay + OverlayEntry 全屏覆盖，CustomPainter 绘制扇形背景，
/// Stack + Positioned 叠加图标和标签，GestureDetector 检测点击落点（极坐标判定）。
///
/// 动画：
/// - 入场：外半径从 innerRadius → outerRadius（easeOutBack 曲线）
/// - 图标/标签在进度 > 0.5 后渐显
/// - 时长：350ms
class RadialMenu extends StatefulWidget {
  /// 中心点（大圆圈圆心）的全局屏幕坐标。
  final Offset center;

  /// 内半径（大圆圈半径，扇形从此处开始）。
  final double innerRadius;

  /// 外半径（扇形结束处）。
  final double outerRadius;

  /// 菜单项列表（建议 2-6 个）。
  final List<RadialMenuItem> items;

  /// 取消回调（点击空白处时触发）。
  final VoidCallback? onCancel;

  const RadialMenu({
    super.key,
    required this.center,
    required this.innerRadius,
    required this.outerRadius,
    required this.items,
    this.onCancel,
  });

  /// 当前活动的 OverlayEntry（单例）。
  static OverlayEntry? _entry;

  /// 通过 [Overlay] 弹出径向菜单。
  static void show(
    BuildContext context, {
    required Offset center,
    required double innerRadius,
    required double outerRadius,
    required List<RadialMenuItem> items,
    VoidCallback? onCancel,
  }) {
    _entry?.remove();
    _entry = OverlayEntry(
      builder: (_) => RadialMenu(
        center: center,
        innerRadius: innerRadius,
        outerRadius: outerRadius,
        items: items,
        onCancel: onCancel,
      ),
    );
    Overlay.of(context, rootOverlay: true).insert(_entry!);
  }

  /// 关闭当前径向菜单。
  static void hide() {
    _entry?.remove();
    _entry = null;
  }

  @override
  State<RadialMenu> createState() => _RadialMenuState();
}

class _RadialMenuState extends State<RadialMenu>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final Animation<double> _scale;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: const Duration(milliseconds: 350),
      vsync: this,
    );
    _scale = CurvedAnimation(parent: _controller, curve: Curves.easeOutBack);
    _controller.forward();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  /// 计算每个菜单项的角度范围。
  /// 均匀分布在下半圆 [0°, 180°]（0°=右侧，180°=左侧）。
  /// 2 项时：碰撞=[90°, 180°]（左下），演化=[0°, 90°]（右下）
  List<_Sector> _computeSectors() {
    final items = widget.items;
    final n = items.length;
    final totalSpan = math.pi; // 180°
    final sectorSpan = totalSpan / n;

    return List.generate(n, (i) {
      final from = i * sectorSpan;
      final to = from + sectorSpan;
      final mid = (from + to) / 2;
      return _Sector(
        item: items[i],
        fromAngle: from,
        toAngle: to,
        midAngle: mid,
      );
    });
  }

  /// 命中测试：判断点击位置是否落在某个扇形内。
  _Sector? _hitTest(Offset tapPos) {
    final dx = tapPos.dx - widget.center.dx;
    final dy = tapPos.dy - widget.center.dy;
    final dist = math.sqrt(dx * dx + dy * dy);
    if (dist < widget.innerRadius || dist > widget.outerRadius) return null;

    final angle = math.atan2(dy, dx); // [-π, π]
    final normalizedAngle = angle < 0 ? angle + 2 * math.pi : angle; // [0, 2π]

    for (final s in _computeSectors()) {
      if (normalizedAngle >= s.fromAngle && normalizedAngle <= s.toAngle) {
        return s;
      }
    }
    return null;
  }

  void _onTapUp(TapUpDetails details) {
    final sector = _hitTest(details.globalPosition);
    if (sector != null) {
      HapticFeedback.mediumImpact();
      RadialMenu.hide();
      sector.item.onTap();
    } else {
      HapticFeedback.lightImpact();
      RadialMenu.hide();
      widget.onCancel?.call();
    }
  }

  @override
  Widget build(BuildContext context) {
    final size = MediaQuery.sizeOf(context);
    final sectors = _computeSectors();

    return Material(
      color: Colors.transparent,
      child: GestureDetector(
        onTapUp: _onTapUp,
        behavior: HitTestBehavior.opaque,
        child: Container(
          width: double.infinity,
          height: double.infinity,
          color: Colors.black.withValues(alpha: 0.5),
          child: AnimatedBuilder(
            animation: _scale,
            builder: (context, child) {
              final currentOuter = widget.innerRadius +
                  (widget.outerRadius - widget.innerRadius) * _scale.value;
              return Stack(
                children: [
                  // 1. 扇形背景层
                  CustomPaint(
                    painter: _RadialMenuPainter(
                      center: widget.center,
                      innerRadius: widget.innerRadius,
                      outerRadius: currentOuter,
                      sectors: sectors,
                    ),
                    size: size,
                  ),
                  // 2. 图标 + 标签层（进度 > 0.5 后渐显）
                  if (_scale.value > 0.5)
                    ..._buildIconLabels(sectors, currentOuter),
                ],
              );
            },
          ),
        ),
      ),
    );
  }

  /// 构建图标和标签的 Positioned widget 列表。
  List<Widget> _buildIconLabels(List<_Sector> sectors, double outerRadius) {
    final textOpacity = ((_scale.value - 0.5) / 0.5).clamp(0.0, 1.0);
    final midRadius = (widget.innerRadius + outerRadius) / 2;

    return sectors.map((s) {
      final midX = widget.center.dx + math.cos(s.midAngle) * midRadius;
      final midY = widget.center.dy + math.sin(s.midAngle) * midRadius;

      return Positioned(
        left: midX - 40,
        top: midY - 30,
        child: Opacity(
          opacity: textOpacity,
          child: SizedBox(
            width: 80,
            height: 60,
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(s.item.icon, color: Colors.white, size: 24),
                const SizedBox(height: 4),
                Text(
                  s.item.label,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    shadows: [
                      Shadow(
                        color: Colors.black54,
                        blurRadius: 4,
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      );
    }).toList();
  }
}

/// 扇形数据。
class _Sector {
  final RadialMenuItem item;
  final double fromAngle;
  final double toAngle;
  final double midAngle;

  const _Sector({
    required this.item,
    required this.fromAngle,
    required this.toAngle,
    required this.midAngle,
  });
}

/// 径向菜单扇形背景绘制器。
class _RadialMenuPainter extends CustomPainter {
  final Offset center;
  final double innerRadius;
  final double outerRadius;
  final List<_Sector> sectors;

  const _RadialMenuPainter({
    required this.center,
    required this.innerRadius,
    required this.outerRadius,
    required this.sectors,
  });

  @override
  void paint(Canvas canvas, Size size) {
    for (final s in sectors) {
      // 构建扇形 Path：外弧 → 内弧
      final sectorPath = Path()
        ..moveTo(
          center.dx + math.cos(s.fromAngle) * innerRadius,
          center.dy + math.sin(s.fromAngle) * innerRadius,
        )
        ..arcTo(
          Rect.fromCircle(center: center, radius: outerRadius),
          s.fromAngle,
          s.toAngle - s.fromAngle,
          false,
        )
        ..lineTo(
          center.dx + math.cos(s.toAngle) * innerRadius,
          center.dy + math.sin(s.toAngle) * innerRadius,
        )
        ..arcTo(
          Rect.fromCircle(center: center, radius: innerRadius),
          s.toAngle,
          s.fromAngle - s.toAngle,
          false,
        )
        ..close();

      // 渐变填充
      final fillPaint = Paint()
        ..shader = RadialGradient(
          center: Alignment.center,
          colors: [
            s.item.color.withValues(alpha: 0.85),
            s.item.color.withValues(alpha: 0.5),
          ],
        ).createShader(
          Rect.fromCircle(center: center, radius: outerRadius),
        );
      canvas.drawPath(sectorPath, fillPaint);

      // 边框
      final borderPaint = Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.5
        ..color = s.item.color.withValues(alpha: 0.6);
      canvas.drawPath(sectorPath, borderPaint);
    }
  }

  @override
  bool shouldRepaint(covariant _RadialMenuPainter oldDelegate) {
    return center != oldDelegate.center ||
        innerRadius != oldDelegate.innerRadius ||
        outerRadius != oldDelegate.outerRadius ||
        sectors != oldDelegate.sectors;
  }
}
