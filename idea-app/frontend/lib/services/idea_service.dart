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

  /// 显式发布已有私有草稿。公开发布必须由作者确认授权条款。
  Future<IdeaResponse> publishIdea({
    required String ideaId,
    required String visibility,
    required String licenseCode,
    String? licenseCustomText,
    String licenseVersion = 'v1',
    bool allowFork = false,
    bool confirmTerms = false,
  }) async {
    try {
      final res = await _dio.post('/ideas/$ideaId/publish', data: {
        'visibility': visibility,
        'license_code': licenseCode,
        'license_custom_text': licenseCustomText,
        'license_version': licenseVersion,
        'allow_fork': allowFork,
        'confirm_terms': confirmTerms,
      });
      return IdeaResponse.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }

  /// 撤回公开发布，恢复为私有草稿。
  Future<void> unpublishIdea(String ideaId) async {
    try {
      await _dio.post('/ideas/$ideaId/unpublish');
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }

  /// 邀请用户访问私有 Idea；接受前不会授予访问权。
  Future<Map<String, dynamic>> inviteToPrivateIdea({
    required String ideaId,
    required String userId,
    String role = 'viewer',
  }) async {
    try {
      final res = await _dio.post('/ideas/$ideaId/invites', data: {
        'user_id': userId,
        'role': role,
      });
      return Map<String, dynamic>.from(res.data as Map);
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }

  Future<Map<String, dynamic>> acceptPrivateIdeaInvite({
    required String ideaId,
    required String inviteId,
  }) async {
    try {
      final res = await _dio.post('/ideas/$ideaId/invites/$inviteId/accept');
      return Map<String, dynamic>.from(res.data as Map);
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }

  Future<Map<String, dynamic>> revokePrivateIdeaInvite({
    required String ideaId,
    required String inviteId,
  }) async {
    try {
      final res = await _dio.delete('/ideas/$ideaId/invites/$inviteId');
      return Map<String, dynamic>.from(res.data as Map);
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
