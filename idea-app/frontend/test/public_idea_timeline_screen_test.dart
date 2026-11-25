import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:dianzi_app/providers/api_provider.dart';
import 'package:dianzi_app/screens/public_idea_timeline_screen.dart';
import 'package:dianzi_app/services/idea_service.dart';

class _FakeIdeaService extends IdeaService {
  _FakeIdeaService(this.versionsByIdea) : super(Dio());

  final Map<String, List<Map<String, dynamic>>> versionsByIdea;
  final List<String> requestedIdeaIds = [];

  @override
  Future<List<Map<String, dynamic>>> getPublicIdeaVersions(
    String ideaId,
  ) async {
    requestedIdeaIds.add(ideaId);
    return versionsByIdea[ideaId] ?? [];
  }
}

Map<String, dynamic> _version(int number) => {
      'id': 'version-$number',
      'version_number': number,
      'content': '版本内容 $number',
      'change_summary': '版本说明 $number',
      'published_at': '2026-11-22T10:00:00Z',
      'attributions': <Map<String, dynamic>>[],
    };

void main() {
  testWidgets('deep link expands and scrolls to a version outside the first screen',
      (tester) async {
    final versions = List.generate(30, (index) => _version(index + 1));
    final service = _FakeIdeaService({'idea-1': versions});

    await tester.pumpWidget(
      ProviderScope(
        overrides: [ideaServiceProvider.overrideWithValue(service)],
        child: const MaterialApp(
          home: PublicIdeaTimelineScreen(
            ideaId: 'idea-1',
            versionId: 'version-30',
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('版本 V30'), findsOneWidget);
    expect(find.text('版本内容 30'), findsOneWidget);
    expect(service.requestedIdeaIds, ['idea-1']);

    final titleTop = tester.getTopLeft(find.text('版本 V30')).dy;
    expect(titleTop, lessThan(tester.view.physicalSize.height /
        tester.view.devicePixelRatio));
  });

  testWidgets('reloads when the route changes to another idea and version',
      (tester) async {
    final service = _FakeIdeaService({
      'idea-1': [_version(1)],
      'idea-2': [_version(2)],
    });

    Widget buildScreen(String ideaId, String versionId) => ProviderScope(
          overrides: [ideaServiceProvider.overrideWithValue(service)],
          child: MaterialApp(
            home: PublicIdeaTimelineScreen(
              key: const ValueKey('timeline'),
              ideaId: ideaId,
              versionId: versionId,
            ),
          ),
        );

    await tester.pumpWidget(buildScreen('idea-1', 'version-1'));
    await tester.pumpAndSettle();
    expect(find.text('版本内容 1'), findsOneWidget);

    await tester.pumpWidget(buildScreen('idea-2', 'version-2'));
    await tester.pumpAndSettle();

    expect(service.requestedIdeaIds, ['idea-1', 'idea-2']);
    expect(find.text('版本内容 2'), findsOneWidget);
    expect(find.text('版本内容 1'), findsNothing);
  });
}
