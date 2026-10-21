"""Validate exclusive CPU allocations and pack a bounded mapper working set."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Region:
    name: str
    start: int
    end: int


def validate_layout(regions: tuple[Region, ...]) -> None:
    """Check half-open allocations, including caller-supplied reservations.

    Each allocation belongs to one 16 KB CPU page. Include existing host/game
    reservations in the same inventory; parent ownership ranges and their child
    allocations are separate inventories, not overlapping entries in one list.
    """
    names, allocated = set(), []
    for region in regions:
        if not isinstance(region, Region):
            raise ValueError('Invalid CPU allocation record')
        if not isinstance(region.name, str) or not region.name.strip() or region.name in names:
            raise ValueError('CPU allocation names must be nonempty and unique')
        if (type(region.start) is not int or type(region.end) is not int
                or not 0 <= region.start < region.end <= 0x10000):
            raise ValueError(f'Invalid CPU allocation range: {region.name}')
        if region.start // 0x4000 != (region.end - 1) // 0x4000:
            raise ValueError(f'CPU allocation crosses its mapper page: {region.name}')
        if any(region.start < other.end and other.start < region.end for other in allocated):
            raise ValueError(f'CPU allocation overlap: {region.name}')
        names.add(region.name)
        allocated.append(region)


def pack_assets(resources: dict[str, bytes], capacity: int = 65536
                ) -> tuple[bytes, dict[str, tuple[int, int]]]:
    """Pack names in stable order, then zero-pad complete 16 KB segments."""
    if type(capacity) is not int or not 0 < capacity <= 65536 or capacity % 16384:
        raise ValueError('Asset capacity must be 1..4 whole mapper segments')
    if not isinstance(resources, dict):
        raise ValueError('Assets require a name-to-bytes mapping')
    for name, data in resources.items():
        if not isinstance(name, str) or not name.strip() or type(data) is not bytes:
            raise ValueError('Asset names must be nonempty strings with immutable byte payloads')
    if sum(map(len, resources.values())) > capacity:
        raise ValueError('Native asset working set exceeds mapper capacity')
    packed, offsets = bytearray(), {}
    for name in sorted(resources):
        data = resources[name]
        offsets[name] = (len(packed), len(data))
        packed.extend(data)
    packed.extend(bytes(capacity - len(packed)))
    return bytes(packed), offsets
