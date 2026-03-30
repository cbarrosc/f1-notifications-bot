from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    """Representa al usuario del bot dentro del dominio."""

    # La entidad de dominio se mantiene inmutable para evitar cambios
    # accidentales una vez construida dentro del caso de uso.
    user_id: int
    first_name: str
    username: str | None
    status: str = "inactive"

    def to_record(self) -> dict[str, int | str | None]:
        """Convierte la entidad al formato persistible esperado por Supabase."""

        # Este formato refleja directamente la estructura esperada por Supabase.
        return {
            "user_id": self.user_id,
            "first_name": self.first_name,
            "username": self.username,
            "status": self.status,
        }
