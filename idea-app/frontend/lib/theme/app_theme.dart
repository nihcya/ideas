import 'package:flutter/material.dart';

/// 点子 App 主题
/// 暗色为主，圆圈颜色在深色背景上更突出
class AppTheme {
  static ThemeData get lightTheme => _buildTheme(Brightness.light);
  static ThemeData get darkTheme => _buildTheme(Brightness.dark);

  static ThemeData _buildTheme(Brightness brightness) {
    final colors = AppColors.forBrightness(brightness);

    final bgColor = colors.background;
    final surfaceColor = colors.surface;
    final cardColor = colors.card;
    final textPrimary = colors.textPrimary;
    final textSecondary = colors.textSecondary;
    final dividerColor = colors.divider;

    return ThemeData(
      useMaterial3: true,
      brightness: brightness,
      scaffoldBackgroundColor: bgColor,
      colorScheme: ColorScheme(
        brightness: brightness,
        primary: colors.gold,
        onPrimary: Colors.black,
        secondary: colors.success,
        onSecondary: Colors.black,
        error: colors.error,
        onError: Colors.white,
        surface: surfaceColor,
        onSurface: textPrimary,
      ),
      cardColor: cardColor,
      dividerColor: dividerColor,
      extensions: [colors],
      appBarTheme: AppBarTheme(
        backgroundColor: bgColor,
        foregroundColor: textPrimary,
        elevation: 0,
        centerTitle: true,
        titleTextStyle: TextStyle(
          color: textPrimary,
          fontSize: 18,
          fontWeight: FontWeight.w600,
        ),
      ),
      textTheme: TextTheme(
        headlineLarge: TextStyle(color: textPrimary, fontWeight: FontWeight.bold),
        headlineMedium: TextStyle(color: textPrimary, fontWeight: FontWeight.w600),
        bodyLarge: TextStyle(color: textPrimary, fontSize: 16),
        bodyMedium: TextStyle(color: textPrimary, fontSize: 14),
        bodySmall: TextStyle(color: textSecondary, fontSize: 12),
        labelLarge: TextStyle(color: textPrimary, fontSize: 14, fontWeight: FontWeight.w600),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: cardColor,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide.none,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: Colors.transparent),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: colors.gold, width: 1.5),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: colors.gold,
          foregroundColor: Colors.black,
          elevation: 0,
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(foregroundColor: colors.gold),
      ),
      bottomNavigationBarTheme: BottomNavigationBarThemeData(
        backgroundColor: surfaceColor,
        selectedItemColor: colors.gold,
        unselectedItemColor: textSecondary,
        type: BottomNavigationBarType.fixed,
        showSelectedLabels: true,
        showUnselectedLabels: true,
        selectedLabelStyle: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600),
        unselectedLabelStyle: const TextStyle(fontSize: 11),
      ),
      iconTheme: IconThemeData(color: textPrimary),
      hintColor: textSecondary,
      // 新增组件主题：消除页面层重复样式
      bottomSheetTheme: BottomSheetThemeData(
        backgroundColor: surfaceColor,
        modalBackgroundColor: surfaceColor,
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
        ),
      ),
      dialogTheme: DialogThemeData(
        backgroundColor: surfaceColor,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: cardColor,
        contentTextStyle: TextStyle(color: textPrimary),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      ),
      floatingActionButtonTheme: FloatingActionButtonThemeData(
        backgroundColor: colors.gold,
        foregroundColor: Colors.black,
        elevation: 2,
      ),
      dividerTheme: DividerThemeData(
        color: dividerColor,
        thickness: 1,
        space: 1,
      ),
    );
  }
}

/// 主题扩展色板：存放 ColorScheme 标准字段之外的语义色。
///
/// 通过 `Theme.of(context).extension<AppColors>()!` 获取，
/// 用于替换散落在各页面里的硬编码 `Color(0xFFxxxxxx)`。
class AppColors extends ThemeExtension<AppColors> {
  /// 主背景（接近纯黑）。
  final Color background;

  /// 一级卡片/底部弹窗/Dialog 背景（深灰）。
  final Color surface;

  /// 二级卡片/输入框背景（次深灰）。
  final Color card;

  /// 分隔线颜色。
  final Color divider;

  /// 主文本色（接近白）。
  final Color textPrimary;

  /// 次要文本色（灰）。
  final Color textSecondary;

  /// 金色（金边圆圈、主按钮、强调）。
  final Color gold;

  /// 错误色（删除、危险操作、倒计时红色）。
  final Color error;

  /// 成功色（草稿保存、收集统计）。
  final Color success;

  /// Fork 相关强调色（被 Fork 统计、演化变体标签）。
  final Color forkAccent;

  /// 谱系图连接线颜色。
  final Color lineageLine;

  /// 碰撞强调色（碰撞按钮主色，蓝紫）。
  final Color collideAccent;

  /// 碰撞按钮渐变第二色（浅蓝紫）。
  final Color collideAccentLight;

  /// 演化强调色（演化按钮主色，绿青）。
  final Color evolveAccent;

  /// 演化按钮渐变第二色（浅绿青）。
  final Color evolveAccentLight;

  /// 碰撞↔演化连接线渐变的青色端。
  final Color linkCyan;

  const AppColors({
    required this.background,
    required this.surface,
    required this.card,
    required this.divider,
    required this.textPrimary,
    required this.textSecondary,
    required this.gold,
    required this.error,
    required this.success,
    required this.forkAccent,
    required this.lineageLine,
    required this.collideAccent,
    required this.collideAccentLight,
    required this.evolveAccent,
    required this.evolveAccentLight,
    required this.linkCyan,
  });

  static const AppColors dark = AppColors(
    background: Color(0xFF0E0E10),
    surface: Color(0xFF1A1A1E),
    card: Color(0xFF242428),
    divider: Color(0xFF2A2A2E),
    textPrimary: Color(0xFFF5F5F7),
    textSecondary: Color(0xFF9A9AA0),
    gold: Color(0xFFFFD700),
    error: Color(0xFFFF5252),
    success: Color(0xFF4ECDC4),
    forkAccent: Color(0xFFB5A8E8),
    lineageLine: Color(0xFF6B6B70),
    collideAccent: Color(0xFF6C5CE7),
    collideAccentLight: Color(0xFFA29BFE),
    evolveAccent: Color(0xFF00B894),
    evolveAccentLight: Color(0xFF55EFC4),
    linkCyan: Color(0xFF00CEC9),
  );

  static const AppColors light = AppColors(
    background: Color(0xFFFAFAFA),
    surface: Colors.white,
    card: Color(0xFFF5F5F7),
    divider: Color(0xFFE5E5EA),
    textPrimary: Color(0xFF1A1A1E),
    textSecondary: Color(0xFF6B6B70),
    gold: Color(0xFFFFD700),
    error: Color(0xFFFF5252),
    success: Color(0xFF4ECDC4),
    forkAccent: Color(0xFFB5A8E8),
    lineageLine: Color(0xFF6B6B70),
    collideAccent: Color(0xFF6C5CE7),
    collideAccentLight: Color(0xFFA29BFE),
    evolveAccent: Color(0xFF00B894),
    evolveAccentLight: Color(0xFF55EFC4),
    linkCyan: Color(0xFF00CEC9),
  );

  static AppColors forBrightness(Brightness b) =>
      b == Brightness.dark ? dark : light;

  /// 便捷获取（暗色场景下永远返回 dark 配色，本应用以暗色为主）。
  static AppColors of(BuildContext context) =>
      Theme.of(context).extension<AppColors>() ?? dark;

  @override
  AppColors copyWith({
    Color? background,
    Color? surface,
    Color? card,
    Color? divider,
    Color? textPrimary,
    Color? textSecondary,
    Color? gold,
    Color? error,
    Color? success,
    Color? forkAccent,
    Color? lineageLine,
    Color? collideAccent,
    Color? collideAccentLight,
    Color? evolveAccent,
    Color? evolveAccentLight,
    Color? linkCyan,
  }) {
    return AppColors(
      background: background ?? this.background,
      surface: surface ?? this.surface,
      card: card ?? this.card,
      divider: divider ?? this.divider,
      textPrimary: textPrimary ?? this.textPrimary,
      textSecondary: textSecondary ?? this.textSecondary,
      gold: gold ?? this.gold,
      error: error ?? this.error,
      success: success ?? this.success,
      forkAccent: forkAccent ?? this.forkAccent,
      lineageLine: lineageLine ?? this.lineageLine,
      collideAccent: collideAccent ?? this.collideAccent,
      collideAccentLight: collideAccentLight ?? this.collideAccentLight,
      evolveAccent: evolveAccent ?? this.evolveAccent,
      evolveAccentLight: evolveAccentLight ?? this.evolveAccentLight,
      linkCyan: linkCyan ?? this.linkCyan,
    );
  }

  @override
  AppColors lerp(ThemeExtension<AppColors>? other, double t) {
    if (other is! AppColors) return this;
    return AppColors(
      background: Color.lerp(background, other.background, t)!,
      surface: Color.lerp(surface, other.surface, t)!,
      card: Color.lerp(card, other.card, t)!,
      divider: Color.lerp(divider, other.divider, t)!,
      textPrimary: Color.lerp(textPrimary, other.textPrimary, t)!,
      textSecondary: Color.lerp(textSecondary, other.textSecondary, t)!,
      gold: Color.lerp(gold, other.gold, t)!,
      error: Color.lerp(error, other.error, t)!,
      success: Color.lerp(success, other.success, t)!,
      forkAccent: Color.lerp(forkAccent, other.forkAccent, t)!,
      lineageLine: Color.lerp(lineageLine, other.lineageLine, t)!,
      collideAccent: Color.lerp(collideAccent, other.collideAccent, t)!,
      collideAccentLight:
          Color.lerp(collideAccentLight, other.collideAccentLight, t)!,
      evolveAccent: Color.lerp(evolveAccent, other.evolveAccent, t)!,
      evolveAccentLight:
          Color.lerp(evolveAccentLight, other.evolveAccentLight, t)!,
      linkCyan: Color.lerp(linkCyan, other.linkCyan, t)!,
    );
  }
}
