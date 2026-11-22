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
    String? query,
    String sort = 'recommended',
    String? licenseCode,
    bool? allowFork,
    String? source,
  }) async {
    try {
      final res = await _dio.get('/ideas/explore', queryParameters: {
        'limit': limit,
        'offset': offset,
        'q': query,
        'sort': sort,
        'license_code': licenseCode,
        'allow_fork': allowFork,
        'source': source,
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

  /// 新建私有草稿（直接创建，非 fork/碰撞/演化）
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

  Future<List<Map<String, dynamic>>> getPendingIdeaInvites() async {
    try {
      final res = await _dio.get('/ideas/invites/inbox');
      return ((res.data as Map<String, dynamic>)['items'] as List<dynamic>)
          .map((item) => Map<String, dynamic>.from(item as Map))
          .toList();
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }

  Future<List<Map<String, dynamic>>> getIdeaInvites(String ideaId) async {
    try {
      final res = await _dio.get('/ideas/$ideaId/invites');
      return ((res.data as Map<String, dynamic>)['items'] as List<dynamic>)
          .map((item) => Map<String, dynamic>.from(item as Map))
          .toList();
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }

  Future<void> declinePrivateIdeaInvite({
    required String ideaId,
    required String inviteId,
  }) async {
    try {
      await _dio.post('/ideas/$ideaId/invites/$inviteId/decline');
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }

  Future<List<Map<String, dynamic>>> getIdeaContributions(String ideaId) async {
    try {
      final res = await _dio.get('/ideas/$ideaId/contributions');
      return ((res.data as Map<String, dynamic>)['items'] as List<dynamic>)
          .map((item) => Map<String, dynamic>.from(item as Map))
          .toList();
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }

  Future<Map<String, dynamic>> submitIdeaContribution({
    required String ideaId,
    required String content,
    String? note,
  }) async {
    try {
      final res = await _dio.post('/ideas/$ideaId/contributions', data: {
        'content': content,
        'note': note,
      });
      return Map<String, dynamic>.from(res.data as Map);
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }

  Future<void> updateIdeaContribution({
    required String ideaId,
    required String contributionId,
    required String content,
    String? note,
  }) async {
    try {
      await _dio.patch('/ideas/$ideaId/contributions/$contributionId', data: {
        'content': content,
        'note': note,
      });
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }

  Future<void> withdrawIdeaContribution({
    required String ideaId,
    required String contributionId,
  }) async {
    try {
      await _dio.delete('/ideas/$ideaId/contributions/$contributionId');
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }

  Future<Map<String, dynamic>> reviewIdeaContribution({
    required String ideaId,
    required String contributionId,
    required String decision,
    String? reviewNote,
  }) async {
    try {
      final res = await _dio.post(
        '/ideas/$ideaId/contributions/$contributionId/review',
        data: {'decision': decision, 'review_note': reviewNote},
      );
      return Map<String, dynamic>.from(res.data as Map);
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }

  Future<List<Map<String, dynamic>>> getIdeaVersions(String ideaId) async {
    try {
      final res = await _dio.get('/ideas/$ideaId/versions');
      return ((res.data as Map<String, dynamic>)['items'] as List<dynamic>)
          .map((item) => Map<String, dynamic>.from(item as Map)).toList();
    } on DioException catch (e) { throw toApiException(e); }
  }


  /// 获取公开创意的只读已发布版本时间线。
  Future<List<Map<String, dynamic>>> getPublicIdeaVersions(String ideaId) async {
    try {
      final res = await _dio.get('/ideas/$ideaId/versions/public');
      final data = res.data as Map<String, dynamic>;
      return ((data['items'] as List<dynamic>?) ?? [])
          .map((item) => Map<String, dynamic>.from(item as Map))
          .toList();
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }

  Future<Map<String, dynamic>> compareIdeaVersions({
    required String ideaId,
    required String versionId,
    required String againstVersionId,
  }) async {
    try {
      final res = await _dio.get(
        '/ideas/$ideaId/versions/$versionId/diff',
        queryParameters: {'against_version_id': againstVersionId},
      );
      return Map<String, dynamic>.from(res.data as Map);
    } on DioException catch (e) { throw toApiException(e); }
  }

  Future<Map<String, dynamic>> createIdeaVersionDraft({
    required String ideaId, required String content, String? changeSummary,
    List<String> contributionIds = const [],
  }) async {
    try {
      final res = await _dio.post('/ideas/$ideaId/versions/drafts', data: {
        'content': content, 'change_summary': changeSummary,
        'contribution_ids': contributionIds,
      });
      return Map<String, dynamic>.from(res.data as Map);
    } on DioException catch (e) { throw toApiException(e); }
  }

  Future<void> updateIdeaVersionDraft({
    required String ideaId, required String versionId, required String content,
    String? changeSummary, List<String> contributionIds = const [],
  }) async {
    try {
      await _dio.patch('/ideas/$ideaId/versions/$versionId', data: {
        'content': content, 'change_summary': changeSummary,
        'contribution_ids': contributionIds,
      });
    } on DioException catch (e) { throw toApiException(e); }
  }

  Future<Map<String, dynamic>> publishIdeaVersion({
    required String ideaId, required String versionId,
  }) async {
    try {
      final res = await _dio.post('/ideas/$ideaId/versions/$versionId/publish');
      return Map<String, dynamic>.from(res.data as Map);
    } on DioException catch (e) { throw toApiException(e); }
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
