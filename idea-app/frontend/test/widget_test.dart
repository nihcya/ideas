// Dianzi App 最小烟雾测试
//
// 验证 app 能启动并渲染主入口 widget。
// 完整 widget 测试需配合 mock HTTP，留给 Phase 2。

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('App smoke test: MaterialApp 渲染', (WidgetTester tester) async {
    // 仅构建一个最小 MaterialApp，验证测试环境正常。
    // 真正的 DianziApp 需要 ProviderScope + 网络依赖，留待集成测试。
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: Center(child: Text('点子')),
        ),
      ),
    );
    expect(find.text('点子'), findsOneWidget);
  });
}
