from __future__ import absolute_import

import logging

from flask import Blueprint, abort

from . import _model
from . import _utils as utils

_LOG = logging.getLogger(__name__)
bp = Blueprint("dataset", __name__, url_prefix="/dataset")

PROVENANCE_DISPLAY_LIMIT = _model.app.config.get(
    "CUBEDASH_PROVENANCE_DISPLAY_LIMIT", 25
)


@bp.route("/<uuid:id_>")
def dataset_page(id_):
    derived_dataset_overflow = source_dataset_overflow = 0

    index = _model.STORE.index
    dataset = index.datasets.get(id_, include_sources=True)

    if dataset is None:
        abort(404, f"No dataset found with id {id_}")

    source_list = list(dataset.metadata.sources.items())
    if len(source_list) > PROVENANCE_DISPLAY_LIMIT:
        source_dataset_overflow = len(source_list) - PROVENANCE_DISPLAY_LIMIT
        source_list = source_list[:PROVENANCE_DISPLAY_LIMIT]

    source_datasets = {
        type_: index.datasets.get(dataset_d["id"]) for type_, dataset_d in source_list
    }

    archived_location_times = index.datasets.get_archived_location_times(id_)

    dataset.metadata.sources = {}
    ordered_metadata = utils.get_ordered_metadata(dataset.metadata_doc)

    derived_datasets = sorted(index.datasets.get_derived(id_), key=utils.dataset_label)
    if len(derived_datasets) > PROVENANCE_DISPLAY_LIMIT:
        derived_dataset_overflow = len(derived_datasets) - PROVENANCE_DISPLAY_LIMIT
        derived_datasets = derived_datasets[:PROVENANCE_DISPLAY_LIMIT]

    return utils.render(
        "dataset.html",
        dataset=dataset,
        dataset_metadata=ordered_metadata,
        derived_datasets=derived_datasets,
        source_datasets=source_datasets,
        archive_location_times=archived_location_times,
        derived_dataset_overflow=derived_dataset_overflow,
        source_dataset_overflow=source_dataset_overflow,
    )
