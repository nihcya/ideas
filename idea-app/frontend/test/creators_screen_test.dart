import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:dianzi_app/providers/api_provider.dart';
import 'package:dianzi_app/screens/creators_screen.dart';
import 'package:dianzi_app/services/user_service.dart';

class _FakeUserService extends UserService {
  _FakeUserService() : super(Dio());

  String? searchedQuery;

  @override
  Future<List<Map<String, dynamic>>> searchPublicCreators(
    String query, {
    int limit = 20,
    int offset = 0,
  }) async {
    searchedQuery = query;
    return [
      {
        'id': 'creator-id',
        'username': 'creator_alice',
        'bio': '专注社区创新',
        'public_idea_count': 4,
        'public_contribution_count': 2,
      },
    ];
  }
}

void main() {
  testWidgets('creator discovery searches and displays public work counts', (tester) async {
    final service = _FakeUserService();
    await tester.pumpWidget(
      ProviderScope(
        overrides: [userServiceProvider.overrideWithValue(service)],
        child: const MaterialApp(home: CreatorsScreen()),
      ),
    );
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField), 'alice');
    await tester.tap(find.byTooltip('搜索'));
    await tester.pumpAndSettle();

    expect(service.searchedQuery, 'alice');
    expect(find.text('creator_alice'), findsOneWidget);
    expect(find.textContaining('公开创意 4'), findsOneWidget);
    expect(find.textContaining('公开贡献 2'), findsOneWidget);
  });
}
