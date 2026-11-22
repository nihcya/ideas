import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:dianzi_app/providers/api_provider.dart';
import 'package:dianzi_app/screens/collaboration_screen.dart';
import 'package:dianzi_app/services/collaboration_service.dart';

class _FakeCollaborationService extends CollaborationService {
  _FakeCollaborationService() : super(Dio());

  String status = 'draft';
  String? invitedUserId;
  bool archived = false;

  @override
  Future<Map<String, dynamic>> get(String id) async => {
        'id': id,
        'title': '异步共创空间',
        'description': '测试空间',
        'status': status,
        'visibility': 'private',
        'owner_id': 'owner-id',
        'member_role': 'owner',
        'members': [
          {
            'user_id': 'owner-id',
            'username': 'owner',
            'role': 'owner',
            'status': 'accepted',
          },
        ],
        'sources': [],
        'contributions': [],
        'events': [],
        'published_result': null,
      };

  @override
  Future<List<Map<String, dynamic>>> searchMembers(String id, String query) async => [
        {'user_id': 'candidate-id', 'username': 'alice'},
      ];

  @override
  Future<void> invite(String id, String userId, String role) async {
    invitedUserId = userId;
  }

  @override
  Future<void> archive(String id) async {
    archived = true;
    status = 'archived';
  }
}

void main() {
  testWidgets('owner can search and select a collaborator to invite', (tester) async {
    final service = _FakeCollaborationService();
    await tester.pumpWidget(
      ProviderScope(
        overrides: [collaborationServiceProvider.overrideWithValue(service)],
        child: const MaterialApp(
          home: CollaborationDetailScreen(collaborationId: 'workspace-id'),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byIcon(Icons.person_add_alt_1).first);
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), 'ali');
    await tester.tap(find.byTooltip('搜索'));
    await tester.pumpAndSettle();

    expect(find.text('alice'), findsOneWidget);
    await tester.tap(find.text('alice'));
    await tester.pumpAndSettle();

    expect(service.invitedUserId, 'candidate-id');
    expect(find.text('邀请已发送，接受前不会获得访问权'), findsOneWidget);
  });

  testWidgets('owner can archive a workspace and sees its read-only state', (tester) async {
    final service = _FakeCollaborationService();
    await tester.pumpWidget(
      ProviderScope(
        overrides: [collaborationServiceProvider.overrideWithValue(service)],
        child: const MaterialApp(
          home: CollaborationDetailScreen(collaborationId: 'workspace-id'),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('归档空间'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('确认归档'));
    await tester.pumpAndSettle();

    expect(service.archived, isTrue);
    expect(find.text('此协作空间已归档'), findsOneWidget);
    expect(find.byTooltip('归档空间'), findsNothing);
  });
}
