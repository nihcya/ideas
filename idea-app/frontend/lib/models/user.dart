/// 用户简要信息（点子详情 author 字段、个人主页用）
class UserBrief {
  final String id;
  final String username;
  final String bio;

  const UserBrief({
    required this.id,
    required this.username,
    this.bio = '',
  });

  factory UserBrief.fromJson(Map<String, dynamic> json) {
    return UserBrief(
      id: json['id'] as String,
      username: json['username'] as String,
      bio: json['bio'] as String? ?? '',
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'username': username,
        'bio': bio,
      };
}

/// 认证结果（注册/登录响应）
class AuthResult {
  final String userId;
  final String username;
  final String token;

  const AuthResult({
    required this.userId,
    required this.username,
    required this.token,
  });

  factory AuthResult.fromJson(Map<String, dynamic> json) {
    return AuthResult(
      userId: json['user_id'] as String,
      username: json['username'] as String,
      token: json['token'] as String,
    );
  }
}

/// 用户主页统计
class UserProfileStats {
  final int produced;
  final int collected;
  final int forkedByOthers;
  final int forkedOthers;
  final int followers;
  final int following;

  const UserProfileStats({
    this.produced = 0,
    this.collected = 0,
    this.forkedByOthers = 0,
    this.forkedOthers = 0,
    this.followers = 0,
    this.following = 0,
  });

  factory UserProfileStats.fromJson(Map<String, dynamic> json) {
    return UserProfileStats(
      produced: json['produced'] as int? ?? 0,
      collected: json['collected'] as int? ?? 0,
      forkedByOthers: json['forked_by_others'] as int? ?? 0,
      forkedOthers: json['forked_others'] as int? ?? 0,
      followers: json['followers'] as int? ?? 0,
      following: json['following'] as int? ?? 0,
    );
  }
}

/// 用户公开主页（思维森林）
class UserProfile {
  final String id;
  final String username;
  final String bio;
  final UserProfileStats stats;
  final bool isSelf;
  final bool isFollowing;
  final bool canFollow;
  final List<UserProfileCircle> circles;

  const UserProfile({
    required this.id,
    required this.username,
    required this.bio,
    required this.stats,
    this.isSelf = false,
    this.isFollowing = false,
    this.canFollow = false,
    required this.circles,
  });

  factory UserProfile.fromJson(Map<String, dynamic> json) {
    return UserProfile(
      id: json['id'] as String,
      username: json['username'] as String,
      bio: json['bio'] as String? ?? '',
      stats: UserProfileStats.fromJson(
        json['stats'] as Map<String, dynamic>? ?? {},
      ),
      isSelf: json['is_self'] as bool? ?? false,
      isFollowing: json['is_following'] as bool? ?? false,
      canFollow: json['can_follow'] as bool? ?? false,
      circles: ((json['circles'] as List<dynamic>?) ?? [])
          .map((e) => UserProfileCircle.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }
}

/// 用户主页圆圈（精简版，无 status / last_touch_at）
class UserProfileCircle {
  final String id;
  final String colorHex;
  final double sizeScore;
  final String borderStyle;

  const UserProfileCircle({
    required this.id,
    required this.colorHex,
    required this.sizeScore,
    required this.borderStyle,
  });

  factory UserProfileCircle.fromJson(Map<String, dynamic> json) {
    return UserProfileCircle(
      id: json['id'] as String,
      colorHex: json['color_hex'] as String,
      sizeScore: (json['size_score'] as num).toDouble(),
      borderStyle: json['border_style'] as String? ?? 'none',
    );
  }
}
