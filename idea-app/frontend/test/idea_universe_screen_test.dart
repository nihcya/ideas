import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:dianzi_app/providers/api_provider.dart';
import 'package:dianzi_app/screens/idea_universe_screen.dart';
import 'package:dianzi_app/services/universe_service.dart';

class _FakeUniverseService extends UniverseService {
  _FakeUniverseService() : super(Dio());

  int calls = 0;
  int lastDepth = 0;
  String lastDirection = '';
  bool lastIncludeInspired = false;
  int addCalls = 0;

  @override
  Future<Map<String, dynamic>> getGraph(
    String ideaId, {
    int depth = 2,
    String direction = 'both',
    bool includeInspired = true,
    int maxNodes = 100,
  }) async {
    calls++;
    lastDepth = depth;
    lastDirection = direction;
    lastIncludeInspired = includeInspired;
    return {
      'root_id': ideaId,
      'can_manage_associations': true,
      'depth': depth,
      'direction': direction,
      'include_inspired': includeInspired,
      'truncated': false,
      'nodes': [
        {
          'id': ideaId,
          'title': '中心创意',
          'color_hex': '#B58B42',
          'author': '作者',
          'depth': 0,
          'node_type': 'idea',
          'navigable': true,
          'is_root': true,
        },
        {
          'id': 'child-1',
          'title': '衍生创意',
          'color_hex': '#4C8DCE',
          'author': '协作者',
          'depth': 1,
          'node_type': 'idea',
          'navigable': true,
          'is_root': false,
        },
        {
          'id': 'restricted:edge-1',
          'title': '已撤回的来源创意',
          'color_hex': '#9CA3AF',
          'author': '历史作者',
          'depth': 1,
          'node_type': 'restricted',
          'navigable': false,
          'is_root': false,
        },
      ],
      'edges': [
        {
          'id': 'edge-1',
          'source': 'child-1',
          'target': ideaId,
          'type': 'fork',
        },
        {
          'id': 'edge-2',
          'source': 'restricted:edge-1',
          'target': ideaId,
          'type': 'fork',
        },
        {
          'id': 'edge-3',
          'source': 'child-1',
          'target': ideaId,
          'type': 'inspired',
          'note': '研究方向启发',
        },
      ],
    };
  }

  @override
  Future<List<Map<String, dynamic>>> searchIdeas(String query, {int limit = 20}) async => [
        {
          'id': 'source-idea',
          'title': '可访问的来源创意',
          'author': '来源作者',
          'color_hex': '#4C8DCE',
        },
      ];

  @override
  Future<void> addInspired({
    required String targetIdeaId,
    required String sourceIdeaId,
    String? note,
  }) async {
    addCalls++;
  }
}

void main() {
  testWidgets('renders bounded graph and restricted non-navigable nodes', (tester) async {
    final service = _FakeUniverseService();

    await tester.pumpWidget(
      ProviderScope(
        overrides: [universeServiceProvider.overrideWithValue(service)],
        child: const MaterialApp(
          home: IdeaUniverseScreen(ideaId: 'root-idea'),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(service.calls, 1);
    expect(find.text('创意宇宙'), findsOneWidget);
    expect(find.text('中心创意'), findsOneWidget);
    expect(find.text('衍生创意'), findsOneWidget);
    expect(find.text('已撤回的来源创意'), findsOneWidget);
    expect(find.text('显示灵感关联'), findsOneWidget);
    expect(find.textContaining('3 个节点'), findsOneWidget);
  });

  testWidgets('owner can search and add an Inspired association', (tester) async {
    final service = _FakeUniverseService();

    await tester.pumpWidget(
      ProviderScope(
        overrides: [universeServiceProvider.overrideWithValue(service)],
        child: const MaterialApp(
          home: IdeaUniverseScreen(ideaId: 'root-idea'),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('管理灵感关联'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('添加灵感来源'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField).first, '人工智能');
    await tester.tap(find.byTooltip('搜索'));
    await tester.pumpAndSettle();
    expect(find.text('可访问的来源创意'), findsOneWidget);
    await tester.tap(find.text('可访问的来源创意'));
    await tester.pumpAndSettle();

    expect(service.addCalls, 1);
  });

  testWidgets('changing Inspired visibility reloads the graph', (tester) async {
    final service = _FakeUniverseService();

    await tester.pumpWidget(
      ProviderScope(
        overrides: [universeServiceProvider.overrideWithValue(service)],
        child: const MaterialApp(
          home: IdeaUniverseScreen(ideaId: 'root-idea'),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byType(SwitchListTile));
    await tester.pumpAndSettle();

    expect(service.calls, 2);
    expect(service.lastIncludeInspired, isFalse);
  });
}
