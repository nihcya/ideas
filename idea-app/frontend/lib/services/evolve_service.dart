import 'package:dio/dio.dart';

import '../models/idea.dart';
import 'api_client.dart';

/// 演化服务：碰撞 / 演化（SAMPER）
class EvolveService {
  final Dio _dio;

  EvolveService(this._dio);

  /// 碰撞两个点子，AI 生成 3 个结合方案
  Future<CollideResponse> collide({
    required String ideaAId,
    required String ideaBId,
  }) async {
    try {
      final res = await _dio.post('/ideas/collide', data: {
        'idea_a_id': ideaAId,
        'idea_b_id': ideaBId,
      });
      return CollideResponse.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }

  /// 碰撞确认 — 用户选定方案后入库
  Future<CollideConfirmResponse> collideConfirm({
    required String ideaAId,
    required String ideaBId,
    required String content,
    bool aiAssisted = true,
  }) async {
    try {
      final res = await _dio.post('/ideas/collide/confirm', data: {
        'idea_a_id': ideaAId,
        'idea_b_id': ideaBId,
        'content': content,
        'ai_assisted': aiAssisted,
      });
      return CollideConfirmResponse.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }

  /// 演化一个点子，选 SAMPER 角度，AI 生成 3 个变体
  Future<EvolveResponse> evolve({
    required String ideaId,
    required String angle,
  }) async {
    try {
      final res = await _dio.post('/ideas/evolve', data: {
        'idea_id': ideaId,
        'angle': angle,
      });
      return EvolveResponse.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }

  /// 演化确认 — 用户选定变体后入库
  Future<EvolveConfirmResponse> evolveConfirm({
    required String parentId,
    required String angle,
    required String content,
    bool aiAssisted = true,
  }) async {
    try {
      final res = await _dio.post('/ideas/evolve/confirm', data: {
        'parent_id': parentId,
        'angle': angle,
        'content': content,
        'ai_assisted': aiAssisted,
      });
      return EvolveConfirmResponse.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }
}
