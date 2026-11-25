import 'package:flutter/material.dart';

import 'user.dart';

/// 圆圈数据（主页 / 仓库画布用）
///
/// 颜色由后端唯一分配，前端只负责渲染 [colorHex]。
class CircleData {
  final String id;
  final String colorHex; // 格式：#RRGGBB
  final double sizeScore; // 0-1，映射到半径 30-60pt
  final bool isOwn;
  final int forkCount;
  final String? borderStyle; // 'gold-thin' / 'none'，主页可能为 null
  final String? status; // 'active' / 'fading' / 'faded'，仓库用

  const CircleData({
    required this.id,
    required this.colorHex,
    required this.sizeScore,
    required this.isOwn,
    required this.forkCount,
    this.borderStyle,
    this.status,
  });

  CircleData copyWith({
    String? id,
    String? colorHex,
    double? sizeScore,
    bool? isOwn,
    int? forkCount,
    String? borderStyle,
    String? status,
  }) {
    return CircleData(
      id: id ?? this.id,
      colorHex: colorHex ?? this.colorHex,
      sizeScore: sizeScore ?? this.sizeScore,
      isOwn: isOwn ?? this.isOwn,
      forkCount: forkCount ?? this.forkCount,
      borderStyle: borderStyle ?? this.borderStyle,
      status: status ?? this.status,
    );
  }

  /// 将 colorHex 解析为 [Color]。
  /// colorHex 格式为 `#RRGGBB`。
  Color get color => Color(int.parse('0xFF${colorHex.substring(1)}'));

  /// 圆圈半径（pt）：30 + sizeScore * 30，即 30-60pt（直径 60-120pt）。
  double get radius => 30.0 + sizeScore * 30.0;

  factory CircleData.fromJson(Map<String, dynamic> json) {
    return CircleData(
      id: json['id'] as String,
      colorHex: json['color_hex'] as String,
      sizeScore: (json['size_score'] as num?)?.toDouble() ?? 0.5,
      isOwn: json['is_own'] as bool? ?? false,
      forkCount: json['fork_count'] as int? ?? 0,
      // 后端已返回 border_style；若未返回，根据 isOwn 兜底推断
      borderStyle: (json['border_style'] as String?) ??
          (json['is_own'] == true ? 'gold-thin' : null),
      status: json['status'] as String?,
    );
  }
}

// ──────────────────────────────────────────────
// 谱系图
// ──────────────────────────────────────────────

/// 谱系图节点
class LineageNode {
  /// Navigable Idea ID, or an opaque lineage key for a withdrawn source.
  final String id;
  final String colorHex; // 格式：#RRGGBB
  final String author;
  final String title;
  final bool isNavigable;
  final String? relationType;
  final Map<String, dynamic>? licenseSnapshot;

  const LineageNode({
    required this.id,
    required this.colorHex,
    required this.author,
    required this.title,
    this.isNavigable = true,
    this.relationType,
    this.licenseSnapshot,
  });

  Color get color => Color(int.parse('0xFF${colorHex.substring(1)}'));

  factory LineageNode.fromJson(Map<String, dynamic> json) {
    return LineageNode(
      id: json['id'] as String,
      colorHex: json['color_hex'] as String,
      author: json['author'] as String? ?? '',
      title: json['title'] as String? ?? '',
      isNavigable: json['is_navigable'] as bool? ?? true,
      relationType: json['relation_type'] as String?,
      licenseSnapshot: json['license_snapshot'] as Map<String, dynamic>?,
    );
  }
}

/// 谱系图数据：父节点（0-2个）+ 子节点（最多10个）
class Lineage {
  final List<LineageNode> parents;
  final List<LineageNode> children;

  const Lineage({
    required this.parents,
    required this.children,
  });

  factory Lineage.fromJson(Map<String, dynamic> json) {
    return Lineage(
      parents: ((json['parents'] as List<dynamic>?) ?? [])
          .map((e) => LineageNode.fromJson(e as Map<String, dynamic>))
          .toList(),
      children: ((json['children'] as List<dynamic>?) ?? [])
          .map((e) => LineageNode.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }
}

// ──────────────────────────────────────────────
// 探索页响应
// ──────────────────────────────────────────────

/// 主页探索页响应
class ExploreResponse {
  final List<CircleData> circles;
  final bool hasMore;

  const ExploreResponse({required this.circles, required this.hasMore});

  factory ExploreResponse.fromJson(Map<String, dynamic> json) {
    return ExploreResponse(
      circles: ((json['circles'] as List<dynamic>?) ?? [])
          .map((e) => CircleData.fromJson(e as Map<String, dynamic>))
          .toList(),
      hasMore: json['has_more'] as bool? ?? false,
    );
  }
}

// ──────────────────────────────────────────────
// 点子详情
// ──────────────────────────────────────────────

/// 点子详情（详情页用）
class IdeaDetail {
  final String id;
  final String content;
  final String colorHex;
  final UserBrief author;
  final DateTime createdAt;
  final int forkCount;
  final bool isInVault;
  final Lineage lineage;
  final String publicationStatus;
  final String visibility;
  final String? licenseCode;
  final String? licenseVersion;
  final String legacyLicenseReviewStatus;
  final DateTime? legacyLicenseReviewDueAt;
  final String? accessRole;
  final bool isForkable;

  const IdeaDetail({
    required this.id,
    required this.content,
    required this.colorHex,
    required this.author,
    required this.createdAt,
    required this.forkCount,
    required this.isInVault,
    required this.lineage,
    this.publicationStatus = 'draft',
    this.visibility = 'private',
    this.licenseCode,
    this.licenseVersion,
    this.legacyLicenseReviewStatus = 'not_required',
    this.legacyLicenseReviewDueAt,
    this.accessRole,
    this.isForkable = false,
  });

  Color get color => Color(int.parse('0xFF${colorHex.substring(1)}'));

  factory IdeaDetail.fromJson(Map<String, dynamic> json) {
    return IdeaDetail(
      id: json['id'] as String,
      content: json['content'] as String,
      colorHex: json['color_hex'] as String,
      author: UserBrief.fromJson(
        json['author'] as Map<String, dynamic>? ?? {},
      ),
      createdAt: DateTime.parse(json['created_at'] as String),
      forkCount: json['fork_count'] as int? ?? 0,
      isInVault: json['is_in_vault'] as bool? ?? false,
      lineage: Lineage.fromJson(
        json['lineage'] as Map<String, dynamic>? ?? {},
      ),
      publicationStatus: json['publication_status'] as String? ?? 'draft',
      visibility: json['visibility'] as String? ?? 'private',
      licenseCode: json['license_code'] as String?,
      licenseVersion: json['license_version'] as String?,
      legacyLicenseReviewStatus:
          json['legacy_license_review_status'] as String? ?? 'not_required',
      legacyLicenseReviewDueAt: json['legacy_license_review_due_at'] == null
          ? null
          : DateTime.parse(json['legacy_license_review_due_at'] as String),
      accessRole: json['access_role'] as String?,
      isForkable: json['is_forkable'] as bool? ?? false,
    );
  }
}

// ──────────────────────────────────────────────
// 发布 / Fork 响应
// ──────────────────────────────────────────────

/// 发布点子响应
class IdeaResponse {
  final String id;
  final String content;
  final String colorHex;
  final String source;
  final String borderStyle;
  final DateTime createdAt;
  final String publicationStatus;
  final String visibility;
  final String? licenseCode;
  final bool allowFork;

  const IdeaResponse({
    required this.id,
    required this.content,
    required this.colorHex,
    required this.source,
    required this.borderStyle,
    required this.createdAt,
    this.publicationStatus = 'draft',
    this.visibility = 'private',
    this.licenseCode,
    this.allowFork = false,
  });

  factory IdeaResponse.fromJson(Map<String, dynamic> json) {
    return IdeaResponse(
      id: json['id'] as String,
      content: json['content'] as String,
      colorHex: json['color_hex'] as String,
      source: json['source'] as String? ?? 'original',
      borderStyle: json['border_style'] as String? ?? 'none',
      createdAt: DateTime.parse(json['created_at'] as String),
      publicationStatus: json['publication_status'] as String? ?? 'draft',
      visibility: json['visibility'] as String? ?? 'private',
      licenseCode: json['license_code'] as String?,
      allowFork: json['allow_fork'] as bool? ?? false,
    );
  }
}

/// Fork 点子响应
class ForkResponse {
  final String id;
  final String parentId;
  final String content;

  const ForkResponse({
    required this.id,
    required this.parentId,
    required this.content,
  });

  factory ForkResponse.fromJson(Map<String, dynamic> json) {
    return ForkResponse(
      id: json['id'] as String,
      parentId: json['parent_id'] as String,
      content: json['content'] as String,
    );
  }
}

// ──────────────────────────────────────────────
// 碰撞 / 演化 AI 响应
// ──────────────────────────────────────────────

/// 碰撞建议
class CollideSuggestion {
  final String type; // 'practical' / 'cross_domain' / 'unconventional'
  final String content;

  const CollideSuggestion({required this.type, required this.content});

  factory CollideSuggestion.fromJson(Map<String, dynamic> json) {
    return CollideSuggestion(
      type: json['type'] as String? ?? 'practical',
      content: json['content'] as String,
    );
  }
}

/// 碰撞响应
class CollideResponse {
  final List<CollideSuggestion> suggestions;

  const CollideResponse({required this.suggestions});

  factory CollideResponse.fromJson(Map<String, dynamic> json) {
    return CollideResponse(
      suggestions: ((json['suggestions'] as List<dynamic>?) ?? [])
          .map((e) => CollideSuggestion.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }
}

/// 演化变体
class EvolveVariant {
  final String distance; // 'near' / 'medium' / 'bold'
  final String content;

  const EvolveVariant({required this.distance, required this.content});

  factory EvolveVariant.fromJson(Map<String, dynamic> json) {
    return EvolveVariant(
      distance: json['distance'] as String? ?? 'medium',
      content: json['content'] as String,
    );
  }
}

/// 演化响应
class EvolveResponse {
  final List<EvolveVariant> variants;

  const EvolveResponse({required this.variants});

  factory EvolveResponse.fromJson(Map<String, dynamic> json) {
    return EvolveResponse(
      variants: ((json['variants'] as List<dynamic>?) ?? [])
          .map((e) => EvolveVariant.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }
}

/// 碰撞确认响应
class CollideConfirmResponse {
  final String id;

  const CollideConfirmResponse({required this.id});

  factory CollideConfirmResponse.fromJson(Map<String, dynamic> json) {
    return CollideConfirmResponse(
      id: json['id'] as String,
    );
  }
}

/// 演化确认响应
class EvolveConfirmResponse {
  final String id;

  const EvolveConfirmResponse({required this.id});

  factory EvolveConfirmResponse.fromJson(Map<String, dynamic> json) {
    return EvolveConfirmResponse(
      id: json['id'] as String,
    );
  }
}
