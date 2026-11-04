# backend/core/case_study_schema.py
# Pydantic model untuk CaseStudy — kontrak output frontend.
# Field sesuai frontend/template/mbg.json (camelCase lewat alias, populate_by_name=True).

from __future__ import annotations

from typing import Optional, Literal
from pydantic import BaseModel, Field, ConfigDict


class MetaInfo(BaseModel):
    peserta: int = Field(..., ge=0)
    ronde: int = Field(..., ge=1)
    sumber: int = Field(..., ge=0)
    tanggal: str

    model_config = ConfigDict(populate_by_name=True)


class DistribusiStance(BaseModel):
    menolak: int = Field(..., ge=0)
    netral: int = Field(..., ge=0)
    mendukung: int = Field(..., ge=0)

    model_config = ConfigDict(populate_by_name=True)


class Hasil(BaseModel):
    vonis: str
    distribusi: DistribusiStance
    alasan: list[str] = Field(default_factory=list)
    kepercayaan: "Kepercayaan"

    model_config = ConfigDict(populate_by_name=True)


class Kepercayaan(BaseModel):
    level: Literal["Rendah", "Rendah–Sedang", "Sedang", "Sedang–Tinggi", "Tinggi"]
    catatan: str

    model_config = ConfigDict(populate_by_name=True)


class Pemicu(BaseModel):
    angka: str
    teks: str

    model_config = ConfigDict(populate_by_name=True)


class Situasi(BaseModel):
    pemicu: Pemicu
    bahan: list[str] = Field(default_factory=list)
    sumber: str

    model_config = ConfigDict(populate_by_name=True)


class Kubu(BaseModel):
    nama: str
    tipe: Literal["tolak", "netral", "dukung"]
    catatan: str
    agen: list[str] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class Kutipan(BaseModel):
    teks: str
    agen: str
    jenis: Literal["langsung", "klaim"]

    model_config = ConfigDict(populate_by_name=True)


class Ronde(BaseModel):
    no: int = Field(..., ge=1)
    judul: str
    ringkas: str
    distribusi: DistribusiStance
    kutipan: Kutipan | None = None

    model_config = ConfigDict(populate_by_name=True)


class TitikBalik(BaseModel):
    agen: str
    dari: Literal["menolak", "netral", "mendukung"]
    ke: Literal["menolak", "netral", "mendukung"]
    kapan: str
    alasan: str

    model_config = ConfigDict(populate_by_name=True)


class BuktiDiperdebatkan(BaseModel):
    agen: str
    teks: str

    model_config = ConfigDict(populate_by_name=True)


class Skenario(BaseModel):
    jika: str
    maka: str

    model_config = ConfigDict(populate_by_name=True)


class WhatIf(BaseModel):
    judul: str
    deskripsi: str
    sebelum: DistribusiStance
    sesudah: Optional["DistribusiStance"] = None

    model_config = ConfigDict(populate_by_name=True)


class Kualitas(BaseModel):
    fallback_count: int = Field(..., ge=0)
    total_giliran: int = Field(..., ge=0)
    fallback_rate: float = Field(..., ge=0.0, le=1.0)
    status: Literal["ok", "degraded", "failed"]

    model_config = ConfigDict(populate_by_name=True)


class CaseStudy(BaseModel):
    """
    Kontrak CaseStudy yang dikembalikan ke frontend.

    Semua field menggunakan camelCase alias (populate_by_name=True).
    Field tambahan jujur (tidak di schema frontend): kualitas, narator_fallback.
    """

    judul: str
    kategori: str
    meta: MetaInfo
    keterbatasan: str
    hasil: Hasil
    situasi: Situasi
    kubu: list[Kubu] = Field(default_factory=list)
    ronde: list[Ronde] = Field(default_factory=list)
    titikBalik: list[TitikBalik] = Field(default_factory=list, alias="titikBalik")
    buktiDiperdebatkan: list[BuktiDiperdebatkan] = Field(default_factory=list, alias="buktiDiperdebatkan")
    skenario: list[Skenario] = Field(default_factory=list)
    whatif: WhatIf | None = None
    # Tambahan jujur — frontend boleh mengabaikan
    kualitas: Kualitas | None = None
    narator_fallback: bool | None = None

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",  # biarkan field tak dikenal lolos saat baca file lama
    )


# Rebuild forward refs
Hasil.model_rebuild()
Kepercayaan.model_rebuild()
WhatIf.model_rebuild()