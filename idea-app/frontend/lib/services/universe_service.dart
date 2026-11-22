import 'package:dio/dio.dart';

import 'api_client.dart';

class UniverseService {
  final Dio _dio;
  UniverseService(this._dio);

  Future<Map<String, dynamic>> getGraph(
    String ideaId, {
    int depth = 2,
    String direction = 'both',
    bool includeInspired = true,
    int maxNodes = 100,
  }) async {
    try {
      final response = await _dio.get(
        '/ideas/$ideaId/graph',
        queryParameters: {
          'depth': depth,
          'direction': direction,
          'include_inspired': includeInspired,
          'max_nodes': maxNodes,
        },
      );
      return Map<String, dynamic>.from(response.data as Map);
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }

  Future<List<Map<String, dynamic>>> searchIdeas(String query, {int limit = 20}) async {
    try {
      final response = await _dio.get(
        '/ideas/search',
        queryParameters: {'q': query, 'limit': limit},
      );
      final data = response.data as Map<String, dynamic>;
      return ((data['items'] as List<dynamic>?) ?? [])
          .map((item) => Map<String, dynamic>.from(item as Map))
          .toList();
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }

  Future<void> addInspired({
    required String targetIdeaId,
    required String sourceIdeaId,
    String? note,
  }) async {
    try {
      await _dio.post('/ideas/$targetIdeaId/associations', data: {
        'source_idea_id': sourceIdeaId,
        'note': note,
      });
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }

  Future<void> removeInspired({
    required String targetIdeaId,
    required String associationId,
  }) async {
    try {
      await _dio.delete('/ideas/$targetIdeaId/associations/$associationId');
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }
}
