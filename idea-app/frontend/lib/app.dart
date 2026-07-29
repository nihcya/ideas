import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'providers/auth_provider.dart';
import 'providers/settings_provider.dart';
import 'routers/app_router.dart';
import 'theme/app_theme.dart';

class DianziApp extends ConsumerWidget {
  const DianziApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(appRouterProvider);
    // S2: 根据用户设置驱动明暗主题；未登录时不加载设置，默认暗色
    final authState = ref.watch(authStateProvider);
    final isLoggedIn = authState.maybeWhen(
      authenticated: (_) => true,
      orElse: () => false,
    );
    final isDark = isLoggedIn
        ? (ref.watch(settingsProvider).value?.darkMode ?? true)
        : true;
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
