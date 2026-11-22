import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:dianzi_app/models/user.dart';
import 'package:dianzi_app/providers/api_provider.dart';
import 'package:dianzi_app/screens/public_user_profile_screen.dart';
import 'package:dianzi_app/services/user_service.dart';

class _FakeUserService extends UserService {
  _FakeUserService() : super(Dio());

  bool following = false;

  @override
  Future<UserProfile> getUserProfile(String id) async => UserProfile(
        id: id,
        username: 'creator',
        bio: '公开创作者',
        stats: UserProfileStats(followers: following ? 1 : 0, following: 3),
        isFollowing: following,
        canFollow: true,
      );

  @override
  Future<Map<String, dynamic>> getUserContributionsPage(
    String userId, {
    int limit = 20,
    int offset = 0,
  }) async => {
        'items': [],
        'total': 0,
        'limit': limit,
        'offset': offset,
        'has_more': false,
      };

  @override
  Future<void> followUser(String userId) async {
    following = true;
  }

  @override
  Future<void> unfollowUser(String userId) async {
    following = false;
  }
}

void main() {
  testWidgets('public creator profile supports follow and reflects new state', (tester) async {
    final service = _FakeUserService();
    await tester.pumpWidget(
      ProviderScope(
        overrides: [userServiceProvider.overrideWithValue(service)],
        child: const MaterialApp(
          home: PublicUserProfileScreen(userId: 'creator-id'),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('关注创作者'), findsOneWidget);
    await tester.tap(find.text('关注创作者'));
    await tester.pumpAndSettle();

    expect(service.following, isTrue);
    expect(find.text('已关注'), findsOneWidget);
    expect(find.textContaining('粉丝 1'), findsOneWidget);
  });
}
