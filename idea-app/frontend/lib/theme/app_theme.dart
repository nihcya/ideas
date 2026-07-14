import 'package:flutter/material.dart';

/// 点子 App 主题
/// 暗色为主，圆圈颜色在深色背景上更突出
class AppTheme {
  static const _primary = Color(0xFFFFD700); // 金色（金边圆圈）
  static const _background = Color(0xFF0E0E10); // 接近纯黑
  static const _surface = Color(0xFF1A1A1E);
  static const _card = Color(0xFF242428);
  static const _textPrimary = Color(0xFFF5F5F7);
  static const _textSecondary = Color(0xFF9A9AA0);

  static ThemeData get lightTheme => _buildTheme(Brightness.light);
  static ThemeData get darkTheme => _buildTheme(Brightness.dark);

  static ThemeData _buildTheme(Brightness brightness) {
    final isDark = brightness == Brightness.dark;
    final bgColor = isDark ? _background : const Color(0xFFFAFAFA);
    final surfaceColor = isDark ? _surface : Colors.white;
    final cardColor = isDark ? _card : const Color(0xFFF5F5F7);
    final textPrimary = isDark ? _textPrimary : const Color(0xFF1A1A1E);
    final textSecondary = isDark ? _textSecondary : const Color(0xFF6B6B70);

    return ThemeData(
      useMaterial3: true,
      brightness: brightness,
      scaffoldBackgroundColor: bgColor,
      colorScheme: ColorScheme(
        brightness: brightness,
        primary: _primary,
        onPrimary: Colors.black,
        secondary: const Color(0xFF4ECDC4),
        onSecondary: Colors.black,
        error: const Color(0xFFFF5252),
        onError: Colors.white,
        surface: surfaceColor,
        onSurface: textPrimary,
      ),
      cardColor: cardColor,
      dividerColor: isDark ? const Color(0xFF2A2A2E) : const Color(0xFFE5E5EA),
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
          borderSide: const BorderSide(color: _primary, width: 1.5),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: _primary,
          foregroundColor: Colors.black,
          elevation: 0,
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(foregroundColor: _primary),
      ),
      bottomNavigationBarTheme: BottomNavigationBarThemeData(
        backgroundColor: surfaceColor,
        selectedItemColor: _primary,
        unselectedItemColor: textSecondary,
        type: BottomNavigationBarType.fixed,
        showSelectedLabels: true,
        showUnselectedLabels: true,
        selectedLabelStyle: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600),
        unselectedLabelStyle: const TextStyle(fontSize: 11),
      ),
      iconTheme: IconThemeData(color: textPrimary),
      hintColor: textSecondary,
    );
  }
}
