import 'package:dio/dio.dart';

import 'api_client.dart';

class CollaborationService {
  final Dio _dio;
  CollaborationService(this._dio);

  Future<List<Map<String, dynamic>>> listMine() async {
    try {
      final res = await _dio.get('/collaborations');
      return ((res.data as Map<String, dynamic>)['items'] as List<dynamic>)
          .map((e) => Map<String, dynamic>.from(e as Map)).toList();
    } on DioException catch (e) { throw toApiException(e); }
  }

  Future<List<Map<String, dynamic>>> getInbox() async {
    try {
      final res = await _dio.get('/collaborations/invitations/inbox');
      return ((res.data as Map<String, dynamic>)['items'] as List<dynamic>)
          .map((e) => Map<String, dynamic>.from(e as Map)).toList();
    } on DioException catch (e) { throw toApiException(e); }
  }

  Future<Map<String, dynamic>> create({
    required String title, String? description, required List<String> sourceIdeaIds,
  }) async {
    try {
      final res = await _dio.post('/collaborations', data: {
        'title': title, 'description': description, 'source_idea_ids': sourceIdeaIds,
      });
      return Map<String, dynamic>.from(res.data as Map);
    } on DioException catch (e) { throw toApiException(e); }
  }

  Future<Map<String, dynamic>> get(String id) async {
    try {
      final res = await _dio.get('/collaborations/$id');
      return Map<String, dynamic>.from(res.data as Map);
    } on DioException catch (e) { throw toApiException(e); }
  }

  Future<void> invite(String id, String userId, String role) async {
    try {
      await _dio.post('/collaborations/$id/members', data: {'user_id': userId, 'role': role});
    } on DioException catch (e) { throw toApiException(e); }
  }

  Future<void> accept(String id) async {
    try { await _dio.post('/collaborations/$id/accept'); }
    on DioException catch (e) { throw toApiException(e); }
  }

  Future<void> decline(String id) async {
    try { await _dio.post('/collaborations/$id/decline'); }
    on DioException catch (e) { throw toApiException(e); }
  }

  Future<void> revoke(String id, String userId) async {
    try { await _dio.delete('/collaborations/$id/members/$userId'); }
    on DioException catch (e) { throw toApiException(e); }
  }

  Future<void> submit(String id, String content, {String type = 'idea', String? note}) async {
    try {
      await _dio.post('/collaborations/$id/contributions', data: {
        'content': content, 'contribution_type': type, 'note': note,
      });
    } on DioException catch (e) { throw toApiException(e); }
  }

  Future<void> review(String id, String contributionId, String decision, {String? note}) async {
    try {
      await _dio.post('/collaborations/$id/contributions/$contributionId/review', data: {
        'decision': decision, 'review_note': note,
      });
    } on DioException catch (e) { throw toApiException(e); }
  }
}
