from typing import Any, Callable, Dict, Tuple, TypeVar, cast, Optional

from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.routing import BaseRoute

CallableT = TypeVar("CallableT", bound=Callable[..., Any])


class VersionedFastAPI(FastAPI):
    def __init__(
        self,
        *args,
        route_version_metadata: Dict[str, str] = {
            "version_format": "{major}.{minor}",
            "prefix_format": "/v{major}_{minor}",
        },
        **extra: Any
    ) -> None:
        super().__init__(*args, **extra)
        self.route_version_mounts: Dict[str, FastAPI] = {}
        self.route_version_metadata = route_version_metadata
        self.route_latest_version = 0

    def version_to_route(
        self,
        route: BaseRoute,
        default_version: Tuple[int, int],
    ) -> Optional[Tuple[Tuple[int, int], APIRoute]]:
        api_route = cast(APIRoute, route)
        if getattr(api_route.endpoint, "_ignore", False):
            return None
        else:
            version = getattr(api_route.endpoint, "_api_version", default_version)
            return version, api_route

    def get(self, *args, route_version: float = 0, **kwds):
        route_version = float(route_version)
        if route_version == 0:
            return super().get(*args, **kwds)

        if route_version > self.route_latest_version:
            self.route_latest_version = route_version

        major, minor = repr(route_version).split(".")

        version_key = self.route_version_metadata["version_format"].format(
            major=major, minor=minor
        )
        if version_key not in self.route_version_mounts:
            prefix = self._get_route_version_prefix(major=major, minor=minor)
            addon = self.new_versioned_mount(self, prefix[1:])
            self.route_version_mounts[version_key] = addon
            self.mount(prefix, addon)

        return self.route_version_mounts[version_key].get(*args, **kwds)

    def _get_route_version_prefix(self, major: str, minor: str):
        return (
            self.route_version_metadata["prefix_format"]
            .format(major=major, minor=minor)
            .replace("_0", "")
        )

    @staticmethod
    def new_versioned_mount(parent: FastAPI, version_key: str) -> FastAPI:
        return FastAPI(
            title=parent.title, description=parent.description, version=version_key
        )

    def enable_latest(self):
        prefix = "/latest"
        major, minor = repr(self.route_latest_version).split(".")
        version_key = self.route_version_metadata["version_format"].format(
            major=major, minor=minor
        )
        latest_app = self.new_versioned_mount(
            self,  f"latest{self._get_route_version_prefix(major, minor)}"
        )
        for route in self.route_version_mounts[version_key].router.routes:
            latest_app.router.routes.append(route)

        self.route_version_mounts["latest"] = latest_app
        self.mount(prefix, latest_app)
