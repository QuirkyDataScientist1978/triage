from collate.collate import Aggregate, Categorical
from collate.spacetime import SpacetimeAggregation
import logging


class FeatureGenerator(object):
    def __init__(self, db_engine, features_schema_name):
        self.db_engine = db_engine
        self.features_schema_name = features_schema_name
        self.categorical_cache = {}

    def _compute_choices(self, choice_query):
        if choice_query not in self.categorical_cache:
            self.categorical_cache[choice_query] = [
                row[0]
                for row
                in self.db_engine.execute(choice_query)
            ]
        return self.categorical_cache[choice_query]

    def _build_choices(self, categorical):
        if 'choices' in categorical:
            return categorical['choices']
        else:
            return self._compute_choices(categorical['choice_query'])

    def _build_categoricals(self, categorical_config):
        return [
            Categorical(
                col=categorical['column'],
                choices=self._build_choices(categorical),
                function=categorical['metrics']
            )
            for categorical in categorical_config
        ]

    def aggregation(self, aggregation_config, feature_dates):
        aggregates = [
            Aggregate(aggregate['quantity'], aggregate['metrics'])
            for aggregate in aggregation_config.get('aggregates', [])
        ]
        logging.info('Found %s quantity aggregates', len(aggregates))
        categoricals = self._build_categoricals(
            aggregation_config.get('categoricals', [])
        )
        logging.info('Found %s categorical aggregates', len(categoricals))
        return SpacetimeAggregation(
            aggregates + categoricals,
            from_obj=aggregation_config['from_obj'],
            intervals=aggregation_config['intervals'],
            groups=aggregation_config['groups'],
            dates=feature_dates,
            date_column=aggregation_config['knowledge_date_column'],
            output_date_column='as_of_date',
            schema=self.features_schema_name,
            prefix=aggregation_config['prefix']
        )

    def _clean_table_name(self, table_name):
        # remove the schema and quotes from the name
        return table_name.split('.')[1].replace('"', "")

    def generate(self, feature_aggregations, feature_dates):
        aggregations = [
            self.aggregation(aggregation_config, feature_dates)
            for aggregation_config in feature_aggregations
        ]
        logging.debug('---------------------')
        logging.debug('---------FEATURE GENERATION------------')
        logging.debug('---------------------')
        for aggregation in aggregations:
            for selectlist in aggregation.get_selects().values():
                for select in selectlist:
                    logging.debug(select)
            aggregation.execute(self.db_engine.connect())
        logging.info('Created %s aggregations', len(aggregations))
        return [
            self._clean_table_name(agg.get_table_name())
            for agg in aggregations
        ]
