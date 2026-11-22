import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../screens/explore_screen.dart';
import '../screens/vault_screen.dart';
import '../screens/spark_screen.dart';
import '../screens/profile_screen.dart';
import '../screens/public_user_profile_screen.dart';
import '../screens/public_idea_timeline_screen.dart';
import '../screens/idea_detail_screen.dart';
import '../screens/collaboration_screen.dart';
import '../screens/universe_screen.dart';
import '../screens/create_idea_screen.dart';
import '../screens/publish_idea_screen.dart';
import '../screens/idea_invites_screen.dart';
import '../screens/manage_idea_invites_screen.dart';
import '../screens/idea_contributions_screen.dart';
import '../screens/idea_versions_screen.dart';
import '../screens/fork_guide_screen.dart';
import '../screens/notifications_screen.dart';
import '../screens/settings_screen.dart';
import '../screens/auth_screen.dart';
import '../providers/auth_provider.dart';

/// 应用路由配置
///
/// 关键设计：
/// - 不使用 `ref.watch(authStateProvider)` 避免每次认证状态变化重建 GoRouter
/// - redirect 中用 `ref.read` 实时读取最新认证状态
/// - 用 `ref.listen` 监听认证状态变化，触发 `router.refresh()` 重新评估路由
final appRouterProvider = Provider<GoRouter>((ref) {
  final router = GoRouter(
    initialLocation: '/explore',
    redirect: (context, state) {
      // 每次导航时读取最新的认证状态
      final authState = ref.read(authStateProvider);
      final isLoading = authState.maybeWhen(
        loading: () => true,
        orElse: () => false,
      );
      final isLoggedIn = authState.maybeWhen(
        authenticated: (_) => true,
        orElse: () => false,
      );

      // 启动加载中，不重定向（等待 token 检查完成）
      if (isLoading) return null;

      final path = state.uri.path;
      final publicPaths = ['/auth', '/explore', '/user/'];
      final isPublic = publicPaths.any((p) => path.startsWith(p)) ||
          (path.startsWith('/idea/') && path.endsWith('/timeline'));

      // 未登录访问受保护页面 → 跳转登录
      if (!isLoggedIn && !isPublic) {
        return '/auth';
      }
      // 已登录访问登录页 → 跳转探索
      if (isLoggedIn && path == '/auth') {
        return '/explore';
      }
      return null;
    },
    routes: [
      // 底部 Tab 页面
      ShellRoute(
        builder: (context, state, child) => MainShell(child: child),
        routes: [
          GoRoute(
            path: '/explore',
            name: 'explore',
            builder: (context, state) => const ExploreScreen(),
          ),
          GoRoute(
            path: '/vault',
            name: 'vault',
            builder: (context, state) => const VaultScreen(),
          ),
          GoRoute(
            path: '/spark',
            name: 'spark',
            builder: (context, state) => const SparkScreen(),
          ),
          GoRoute(
            path: '/profile',
            name: 'profile',
            builder: (context, state) => const ProfileScreen(),
          ),
        ],
      ),
      GoRoute(
        path: '/collaborations',
        name: 'collaborations',
        builder: (context, state) => const CollaborationListScreen(),
      ),
      GoRoute(
        path: '/collaborations/:id',
        name: 'collaborationDetail',
        builder: (context, state) => CollaborationDetailScreen(
          collaborationId: state.pathParameters['id']!,
        ),
      ),
      // 独立页面（push 跳转）
      GoRoute(
        path: '/auth',
        name: 'auth',
        builder: (context, state) => const AuthScreen(),
      ),
      GoRoute(
        path: '/user/:id',
        name: 'publicUserProfile',
        builder: (context, state) => PublicUserProfileScreen(
          userId: state.pathParameters['id']!,
        ),
      ),
      GoRoute(
        path: '/idea/:id/universe',
        name: 'ideaUniverse',
        builder: (context, state) => UniverseScreen(
          ideaId: state.pathParameters['id']!,
        ),
      ),
      GoRoute(
        path: '/idea/:id/timeline',
        name: 'publicIdeaTimeline',
        builder: (context, state) => PublicIdeaTimelineScreen(
          ideaId: state.pathParameters['id']!,
          versionId: state.uri.queryParameters['version'],
        ),
      ),
      GoRoute(
        path: '/idea/:id',
        name: 'ideaDetail',
        builder: (context, state) => IdeaDetailScreen(
          ideaId: state.pathParameters['id']!,
        ),
      ),
      GoRoute(
        path: '/invites',
        name: 'ideaInvites',
        builder: (context, state) => const IdeaInvitesScreen(),
      ),
      GoRoute(
        path: '/idea/:id/contributions',
        name: 'ideaContributions',
        builder: (context, state) => IdeaContributionsScreen(
          ideaId: state.pathParameters['id']!,
          isOwner: state.uri.queryParameters['owner'] == 'true',
        ),
      ),
      GoRoute(
        path: '/idea/:id/versions',
        name: 'ideaVersions',
        builder: (context, state) => IdeaVersionsScreen(ideaId: state.pathParameters['id']!, highlightVersionId: state.uri.queryParameters['version']),
      ),
      GoRoute(
        path: '/idea/:id/invites',
        name: 'manageIdeaInvites',
        builder: (context, state) => ManageIdeaInvitesScreen(
          ideaId: state.pathParameters['id']!,
        ),
      ),
      GoRoute(
        path: '/idea/:id/publish',
        name: 'publishIdea',
        builder: (context, state) => PublishIdeaScreen(
          ideaId: state.pathParameters['id']!,
        ),
      ),
      GoRoute(
        path: '/create',
        name: 'create',
        builder: (context, state) => const CreateIdeaScreen(),
      ),
      GoRoute(
        path: '/fork/:id',
        name: 'forkGuide',
        builder: (context, state) => ForkGuideScreen(
          parentId: state.pathParameters['id']!,
        ),
      ),
      GoRoute(
        path: '/notifications',
        name: 'notifications',
        builder: (context, state) => const NotificationsScreen(),
      ),
      GoRoute(
        path: '/settings',
        name: 'settings',
        builder: (context, state) => const SettingsScreen(),
      ),
    ],
  );

  // 监听认证状态变化，触发路由重新评估
  // 当 setAuthenticated / setUnauthenticated 被调用时，
  // router.refresh() 会让 GoRouter 重新执行 redirect 逻辑
  ref.listen(authStateProvider, (_, __) {
    router.refresh();
  });

  return router;
});

/// 底部导航 Shell（探索 / 仓库 / 一点 / 我）
class MainShell extends StatelessWidget {
  final Widget child;
  const MainShell({super.key, required this.child});

  int _currentIndex(BuildContext context) {
    final location = GoRouterState.of(context).uri.path;
    if (location.startsWith('/vault')) return 1;
    if (location.startsWith('/spark')) return 2;
    if (location.startsWith('/profile')) return 3;
    return 0;
  }

  @override
  Widget build(BuildContext context) {
    final idx = _currentIndex(context);
    return Scaffold(
      body: child,
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: idx,
        onTap: (i) {
          switch (i) {
            case 0: context.go('/explore');
            case 1: context.go('/vault');
            case 2: context.go('/spark');
            case 3: context.go('/profile');
          }
        },
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.explore_outlined), activeIcon: Icon(Icons.explore), label: '探索'),
          BottomNavigationBarItem(icon: Icon(Icons.inventory_2_outlined), activeIcon: Icon(Icons.inventory_2), label: '仓库'),
          BottomNavigationBarItem(icon: Icon(Icons.bolt_outlined), activeIcon: Icon(Icons.bolt), label: '一点'),
          BottomNavigationBarItem(icon: Icon(Icons.person_outline), activeIcon: Icon(Icons.person), label: '我'),
        ],
      ),
    );
  }
}
