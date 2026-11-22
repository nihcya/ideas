import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:dianzi_app/providers/api_provider.dart';
import 'package:dianzi_app/screens/admin_reports_screen.dart';
import 'package:dianzi_app/services/idea_service.dart';

class _FakeIdeaService extends IdeaService {
  _FakeIdeaService() : super(Dio());

  String? reviewedStatus;
  bool? hidIdea;

  @override
  Future<List<Map<String, dynamic>>> getAdminReports({
    String status = 'pending',
    int limit = 30,
    int offset = 0,
  }) async => [
        {
          'id': 'report-id',
          'idea_id': 'idea-id',
          'idea_content': '公开创意内容',
          'reporter_username': 'reporter',
          'reason': 'copyright',
          'description': '疑似未经授权使用',
          'status': status,
          'resolution_note': null,
          'action_taken': 'none',
        },
      ];

  @override
  Future<void> reviewReport({
    required String reportId,
    required String status,
    required bool hideIdea,
    String? resolutionNote,
  }) async {
    reviewedStatus = status;
    hidIdea = hideIdea;
  }
}

void main() {
  testWidgets('admin can review a report and hide the reported public Idea', (tester) async {
    final service = _FakeIdeaService();
    await tester.pumpWidget(
      ProviderScope(
        overrides: [ideaServiceProvider.overrideWithValue(service)],
        child: const MaterialApp(home: AdminReportsScreen()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('公开创意内容'), findsOneWidget);
    await tester.tap(find.text('处理'));
    await tester.pumpAndSettle();

    await tester.tap(find.byType(DropdownButtonFormField<String>));
    await tester.pumpAndSettle();
    await tester.tap(find.text('已处理').last);
    await tester.pumpAndSettle();

    await tester.tap(find.text('同时将创意下架并转为私有草稿'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('提交处理'));
    await tester.pumpAndSettle();

    expect(service.reviewedStatus, 'resolved');
    expect(service.hidIdea, isTrue);
    expect(find.text('举报处理结果已保存'), findsOneWidget);
  });
}
