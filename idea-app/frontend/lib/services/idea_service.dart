import 'package:dio/dio.dart';

import '../models/idea.dart';
import 'api_client.dart';

/// 点子服务：探索 / 详情 / 发布 / Fork
class IdeaService {
  final Dio _dio;

  IdeaService(this._dio);

  /// 主页探索页 — 获取一批圆圈（90%随机 + 10%热门）
  Future<ExploreResponse> getExplore({
    int limit = 25,
    int offset = 0,
  }) async {
    try {
      final res = await _dio.get('/ideas/explore', queryParameters: {
        'limit': limit,
        'offset': offset,
      });
      return ExploreResponse.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }

  /// 点子详情页 — 获取完整内容 + 谱系图（2层）
  Future<IdeaDetail> getIdeaDetail(String id) async {
    try {
      final res = await _dio.get('/ideas/$id');
      return IdeaDetail.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }

  /// 发布新点子（直接发布，非 fork/碰撞/演化）
  Future<IdeaResponse> createIdea(String content) async {
    try {
      final res = await _dio.post('/ideas', data: {
        'content': content,
      });
      return IdeaResponse.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }

  /// Fork 一个点子（联想引导后提交）
  Future<ForkResponse> forkIdea({
    required String parentId,
    required String content,
  }) async {
    try {
      final res = await _dio.post('/ideas/fork', data: {
        'parent_id': parentId,
        'content': content,
      });
      return ForkResponse.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }
}
