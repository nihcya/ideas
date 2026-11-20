import 'package:flutter_test/flutter_test.dart';

import 'package:dianzi_app/models/idea.dart';

void main() {
  group('IdeaDetail publication metadata', () {
    final baseJson = <String, dynamic>{
      'id': 'idea-1',
      'content': 'A private draft',
      'color_hex': '#123456',
      'author': {'id': 'user-1', 'username': 'author', 'bio': ''},
      'created_at': '2026-11-20T10:00:00Z',
      'fork_count': 0,
      'is_in_vault': true,
      'lineage': {'parents': [], 'children': []},
    };

    test('defaults older API responses to private draft with no derivative rights', () {
      final idea = IdeaDetail.fromJson(baseJson);

      expect(idea.publicationStatus, 'draft');
      expect(idea.visibility, 'private');
      expect(idea.licenseCode, isNull);
      expect(idea.isForkable, isFalse);
    });

    test('reads publication and derivative metadata from V2 response', () {
      final idea = IdeaDetail.fromJson({
        ...baseJson,
        'publication_status': 'published',
        'visibility': 'public',
        'license_code': 'attribution_adaptation',
        'license_version': 'v1',
        'is_forkable': true,
      });

      expect(idea.publicationStatus, 'published');
      expect(idea.visibility, 'public');
      expect(idea.licenseCode, 'attribution_adaptation');
      expect(idea.licenseVersion, 'v1');
      expect(idea.isForkable, isTrue);
    });
  });

  test('IdeaResponse parses default-private create response', () {
    final response = IdeaResponse.fromJson({
      'id': 'idea-2',
      'content': 'Draft',
      'color_hex': '#654321',
      'source': 'ugc',
      'author_id': 'user-1',
      'created_at': '2026-11-20T10:00:00Z',
      'border_style': 'gold-thin',
      'publication_status': 'draft',
      'visibility': 'private',
      'allow_fork': false,
    });

    expect(response.publicationStatus, 'draft');
    expect(response.visibility, 'private');
    expect(response.allowFork, isFalse);
  });
}
