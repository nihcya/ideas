import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'providers/settings_provider.dart';
import 'routers/app_router.dart';
import 'theme/app_theme.dart';

class DianziApp extends ConsumerWidget {
  const DianziApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(appRouterProvider);
    // S2: 根据用户设置驱动明暗主题；设置未加载完成前默认暗色
    final settingsAsync = ref.watch(settingsProvider);
    final isDark = settingsAsync.value?.darkMode ?? true;
    return MaterialApp.router(
      title: '点子',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme,
      darkTheme: AppTheme.darkTheme,
      themeMode: isDark ? ThemeMode.dark : ThemeMode.light,
      routerConfig: router,
    );
  }
}
