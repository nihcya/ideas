from pydantic import BaseModel, Field


class NotificationPreferenceItem(BaseModel):
    notification_type: str = Field(min_length=1, max_length=32)
    enabled: bool


class NotificationPreferencesResponse(BaseModel):
    items: list[NotificationPreferenceItem]


class NotificationPreferencesUpdateRequest(BaseModel):
    items: list[NotificationPreferenceItem] = Field(min_length=1, max_length=20)
