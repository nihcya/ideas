import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:dianzi_app/models/idea.dart';
import 'package:dianzi_app/providers/api_provider.dart';
import 'package:dianzi_app/providers/explore_provider.dart';
import 'package:dianzi_app/services/idea_service.dart';

class _FakeIdeaService extends IdeaService {
  _FakeIdeaService() : super(Dio());

  final calls = <Map<String, dynamic>>[];
  bool failNextPage = false;

  @override
  Future<ExploreResponse> getExplore({
    int limit = 25,
    int offset = 0,
    String? query,
    String sort = 'recommended',
    String? licenseCode,
    bool? allowFork,
    String? source,
  }) async {
    calls.add({
      'limit': limit,
      'offset': offset,
      'query': query,
      'sort': sort,
      'licenseCode': licenseCode,
      'allowFork': allowFork,
      'source': source,
    });
    if (failNextPage && offset > 0) {
      throw Exception('network unavailable');
    }
    return ExploreResponse(
      circles: [
        CircleData(
          id: 'idea-$offset',
          colorHex: '#123456',
          sizeScore: 0.5,
          isOwn: false,
          forkCount: 0,
        ),
      ],
      hasMore: offset == 0,
    );
  }
}

void main() {
  test('filters are preserved across refresh and pagination', () async {
    final service = _FakeIdeaService();
    final container = ProviderContainer(
      overrides: [ideaServiceProvider.overrideWithValue(service)],
    );
    addTearDown(container.dispose);

    await container.read(exploreProvider.future);
    await container.read(exploreProvider.notifier).setFilters(
          const ExploreFilters(
            query: '人工智能',
            sort: 'latest',
            licenseCode: 'attribution_adaptation',
            allowFork: true,
            source: 'fork',
          ),
        );

    expect(service.calls.last['query'], '人工智能');
    expect(service.calls.last['sort'], 'latest');
    expect(service.calls.last['licenseCode'], 'attribution_adaptation');
    expect(service.calls.last['allowFork'], true);
    expect(service.calls.last['source'], 'fork');

    await container.read(exploreProvider.notifier).loadMore();
    expect(service.calls.last['offset'], 1);
    expect(service.calls.last['query'], '人工智能');
    expect(service.calls.last['sort'], 'latest');
    expect(service.calls.last['allowFork'], true);
  });

  test('load-more failure keeps already loaded Explore circles', () async {
    final service = _FakeIdeaService()..failNextPage = true;
    final container = ProviderContainer(
      overrides: [ideaServiceProvider.overrideWithValue(service)],
    );
    addTearDown(container.dispose);

    await container.read(exploreProvider.future);
    await expectLater(
      container.read(exploreProvider.notifier).loadMore(),
      throwsA(isA<Exception>()),
    );
    final circles = container.read(exploreProvider).valueOrNull;
    expect(circles, hasLength(1));
    expect(circles!.single.id, 'idea-0');
  });
}
