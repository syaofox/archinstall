from pathlib import Path
from typing import assert_never, override

from archinstall.lib.menu.helpers import Input, Selection
from archinstall.lib.menu.list_manager import ListManager
from archinstall.lib.menu.util import prompt_dir
from archinstall.lib.models.device import BtrfsMountOption, SubvolumeModification
from archinstall.lib.translationhandler import tr
from archinstall.tui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.result import ResultType


class SubvolumeMenu(ListManager[SubvolumeModification]):
	def __init__(
		self,
		btrfs_subvols: list[SubvolumeModification],
		prompt: str | None = None,
		default_mount_options: list[str] = [],
	):
		self._actions = [
			tr('Add subvolume'),
			tr('Edit subvolume'),
			tr('Delete subvolume'),
		]
		self._default_mount_options = default_mount_options

		super().__init__(
			btrfs_subvols,
			[self._actions[0]],
			self._actions[1:],
			prompt,
		)

	async def show(self) -> list[SubvolumeModification] | None:
		return await super()._run()

	@override
	def selected_action_display(self, selection: SubvolumeModification) -> str:
		return str(selection.name)

	async def _select_mount_options(
		self,
		subvol_name: str,
		preset_options: list[str] = [],
	) -> list[str]:
		header = f'{tr("Subvolume")}: {subvol_name}\n'
		header += tr('Would you like to use compression or disable CoW?')
		compression = tr('Use compression')
		disable_cow = tr('Disable Copy-on-Write')
		skip_label = tr('Skip')

		items = [
			MenuItem(compression, value=BtrfsMountOption.compress.value),
			MenuItem(disable_cow, value=BtrfsMountOption.nodatacow.value),
			MenuItem(skip_label, value=''),
		]

		preset = ''
		if BtrfsMountOption.compress.value in preset_options:
			preset = BtrfsMountOption.compress.value
		elif BtrfsMountOption.nodatacow.value in preset_options:
			preset = BtrfsMountOption.nodatacow.value

		group = MenuItemGroup(items, sort_items=False)
		if preset:
			group.set_focus_by_value(preset)

		result = await Selection[str](
			group,
			header=header,
			allow_skip=False,
		).show()

		match result.type_:
			case ResultType.Selection:
				value = result.get_value()
				return [value] if value else []
			case _:
				return []

	async def _add_subvolume(self, preset: SubvolumeModification | None = None) -> SubvolumeModification | None:
		def validate(value: str | None) -> str | None:
			if value:
				return None
			return tr('Value cannot be empty')

		result = await Input(
			header=tr('Enter subvolume name'),
			allow_skip=True,
			default_value=str(preset.name) if preset else None,
			validator_callback=validate,
		).show()

		match result.type_:
			case ResultType.Skip:
				return preset
			case ResultType.Selection:
				name = result.get_value()
			case ResultType.Reset:
				raise ValueError('Unhandled result type')
			case _:
				assert_never(result.type_)

		header = f'{tr("Subvolume name")}: {name}\n\n'
		header += tr('Enter subvolume mountpoint')

		path = await prompt_dir(
			header=header,
			allow_skip=True,
			validate=True,
			must_exist=False,
		)

		if not path:
			return preset

		preset_options = preset.mount_options if preset else self._default_mount_options
		mount_options = await self._select_mount_options(name, preset_options)

		return SubvolumeModification(Path(name), path, mount_options)

	@override
	async def handle_action(
		self,
		action: str,
		entry: SubvolumeModification | None,
		data: list[SubvolumeModification],
	) -> list[SubvolumeModification]:
		if action == self._actions[0]:
			new_subvolume = await self._add_subvolume()

			if new_subvolume is not None:
				# in case a user with the same username as an existing user
				# was created we'll replace the existing one
				data = [d for d in data if d.name != new_subvolume.name]
				data += [new_subvolume]
		elif entry is not None:
			if action == self._actions[1]:
				new_subvolume = await self._add_subvolume(entry)

				if new_subvolume is not None:
					# we'll remove the original subvolume and add the modified version
					data = [d for d in data if d.name != entry.name and d.name != new_subvolume.name]
					data += [new_subvolume]
			elif action == self._actions[2]:
				data = [d for d in data if d != entry]

		return data
