from pydantic import BaseModel, ConfigDict, Field


class PublicAdvertisement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    public_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    caption: str = Field(default="", max_length=2000)
    owner_public_id: str = Field(default="", max_length=64)
    desktop_image_url: str = Field(default="", max_length=2048)
    mobile_image_url: str = Field(default="", max_length=2048)
    crop_x: float = Field(default=50.0, ge=0, le=100)
    crop_y: float = Field(default=50.0, ge=0, le=100)
    crop_zoom: float = Field(default=1.0, gt=0)

