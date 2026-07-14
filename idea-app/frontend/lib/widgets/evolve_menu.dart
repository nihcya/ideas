import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// 弹出演化菜单（顶级函数，便于直接调用）。
///
/// 用法：`showEvolveMenu(context, onCollide: ..., onEvolve: ...)`
Future<void> showEvolveMenu(
  BuildContext context, {
  required VoidCallback onCollide,
  required VoidCallback onEvolve,
}) {
  return showModalBottomSheet(
    context: context,
    backgroundColor: Colors.transparent,
    isScrollControlled: true,
    builder: (_) => EvolveMenu(onCollide: onCollide, onEvolve: onEvolve),
  );
}

/// 演化菜单（底部弹出）。
///
/// 遵循 TECH_CONSTRAINTS 1.4：
/// - 点击选项时触发 HapticFeedback.mediumImpact()
/// - 漫步动效：选项之间有步行动画，每步触发 HapticFeedback.lightImpact()
///
/// 两个选项：
/// - **碰撞**（蓝紫色系）→ [onCollide]
/// - **演化**（绿青色系）→ [onEvolve]
class EvolveMenu extends StatefulWidget {
  final VoidCallback onCollide;
  final VoidCallback onEvolve;

  const EvolveMenu({
    super.key,
    required this.onCollide,
    required this.onEvolve,
  });

  /// 通过 [showModalBottomSheet] 弹出演化菜单。
  static Future<void> show(
    BuildContext context, {
    required VoidCallback onCollide,
    required VoidCallback onEvolve,
  }) {
    return showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (_) => EvolveMenu(onCollide: onCollide, onEvolve: onEvolve),
    );
  }

  @override
  State<EvolveMenu> createState() => _EvolveMenuState();
}

class _EvolveMenuState extends State<EvolveMenu>
    with TickerProviderStateMixin {
  /// 漫步动效控制器：4秒一个完整来回（0→1→0）。
  late final AnimationController _walkController;

  /// 上一次触发的步数（用于检测步进边界）。
  int _lastStep = -1;

  @override
  void initState() {
    super.initState();
    _walkController = AnimationController(
      duration: const Duration(seconds: 4),
      vsync: this,
    )..repeat();
    _walkController.addListener(_onWalkTick);
  }

  void _onWalkTick() {
    // 8 步完整来回（4 步向右 + 4 步向左）
    final step = (_walkController.value * 8).floor() % 8;
    if (step != _lastStep) {
      _lastStep = step;
      HapticFeedback.lightImpact();
    }
  }

  @override
  void dispose() {
    _walkController.removeListener(_onWalkTick);
    _walkController.dispose();
    super.dispose();
  }

  void _onCollide() {
    HapticFeedback.mediumImpact();
    widget.onCollide();
  }

  void _onEvolve() {
    HapticFeedback.mediumImpact();
    widget.onEvolve();
  }

  /// 漫步标记的横向位置（0 = 左端碰撞，1 = 右端演化）。
  double get _markerT {
    final t = _walkController.value;
    return t < 0.5 ? t * 2 : (1 - t) * 2;
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        color: Color(0xFF1A1A1E),
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      padding: const EdgeInsets.fromLTRB(24, 32, 24, 48),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            '选择演化方式',
            style: Theme.of(context).textTheme.headlineMedium,
          ),
          const SizedBox(height: 8),
          Text(
            '让点子碰撞出火花，或演化出新的方向',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 36),
          AnimatedBuilder(
            animation: _walkController,
            builder: (context, _) {
              return _buildOptions(context);
            },
          ),
        ],
      ),
    );
  }

  Widget _buildOptions(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final maxW = constraints.maxWidth;
        const buttonSize = 100.0;
        const gap = 40.0;
        final totalWidth = buttonSize * 2 + gap;
        final leftCenter = buttonSize / 2;
        final rightCenter = buttonSize + gap + buttonSize / 2;
        final startX = (maxW - totalWidth) / 2;

        // 漫步标记位置（在两按钮之间的连接线上）
        final markerX = startX +
            leftCenter +
            (rightCenter - leftCenter) * _markerT;
        const markerY = buttonSize / 2;

        return SizedBox(
          width: maxW,
          height: buttonSize + 20,
          child: Stack(
            clipBehavior: Clip.none,
            children: [
              // 连接线
              Positioned(
                left: startX + leftCenter,
                top: markerY,
                child: Container(
                  width: rightCenter - leftCenter,
                  height: 2,
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [
                        const Color(0xFF6C5CE7).withValues(alpha: 0.6),
                        const Color(0xFF00CEC9).withValues(alpha: 0.6),
                      ],
                    ),
                  ),
                ),
              ),
              // 漫步标记（步行的光点）
              Positioned(
                left: markerX - 6,
                top: markerY - 6,
                child: Container(
                  width: 12,
                  height: 12,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: Colors.white.withValues(alpha: 0.9),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.white.withValues(alpha: 0.4),
                        blurRadius: 8,
                        spreadRadius: 1,
                      ),
                    ],
                  ),
                ),
              ),
              // 碰撞按钮（蓝紫色系）
              Positioned(
                left: startX,
                top: 0,
                child: _buildOptionButton(
                  label: '碰撞',
                  icon: Icons.bolt,
                  colors: const [Color(0xFF6C5CE7), Color(0xFFA29BFE)],
                  onTap: _onCollide,
                ),
              ),
              // 演化按钮（绿青色系）
              Positioned(
                left: startX + buttonSize + gap,
                top: 0,
                child: _buildOptionButton(
                  label: '演化',
                  icon: Icons.eco,
                  colors: const [Color(0xFF00B894), Color(0xFF55EFC4)],
                  onTap: _onEvolve,
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildOptionButton({
    required String label,
    required IconData icon,
    required List<Color> colors,
    required VoidCallback onTap,
  }) {
    const size = 100.0;
    return GestureDetector(
      onTap: onTap,
      child: Column(
        children: [
          Container(
            width: size,
            height: size,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: colors,
              ),
              boxShadow: [
                BoxShadow(
                  color: colors[0].withValues(alpha: 0.4),
                  blurRadius: 16,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: Icon(icon, color: Colors.white, size: 36),
          ),
          const SizedBox(height: 8),
          Text(
            label,
            style: const TextStyle(
              color: Color(0xFFF5F5F7),
              fontSize: 14,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}
