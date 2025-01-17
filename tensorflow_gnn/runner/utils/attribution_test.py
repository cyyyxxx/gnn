"""Tests for attribution."""
import tensorflow as tf
import tensorflow_gnn as tfgnn

from tensorflow_gnn.runner import orchestration
from tensorflow_gnn.runner.utils import attribution

IntegratedGradientsExporter = attribution.IntegratedGradientsExporter
ModelExporter = orchestration.ModelExporter


class AttributionTest(tf.test.TestCase):

  gt = tfgnn.GraphTensor.from_pieces(
      context=tfgnn.Context.from_fields(features={
          "h": tf.constant((514, 433), dtype=tf.float32),
      }),
      node_sets={
          "node":
              tfgnn.NodeSet.from_fields(
                  features={
                      "h": tf.constant((8191, 9474, 1634), dtype=tf.float32),
                  },
                  sizes=tf.constant((3,), dtype=tf.int32),
              ),
      },
      edge_sets={
          "edge":
              tfgnn.EdgeSet.from_fields(
                  features={"weight": tf.constant((153, 9), dtype=tf.float32)},
                  sizes=tf.constant((2,), dtype=tf.int32),
                  adjacency=tfgnn.Adjacency.from_indices(
                      source=("node", (0, 1)), target=("node", (1, 2))),
              ),
      },
  )

  def test_counterfactual_random(self):
    counterfactual = attribution.counterfactual(self.gt, random=True, seed=8191)

    self.assertAllEqual(
        counterfactual.context.features["h"],
        tf.constant((492.80963, 466.38303), dtype=tf.float32))

    self.assertAllEqual(
        counterfactual.edge_sets["edge"].features["weight"],
        tf.constant((134.47087, 66.30827), dtype=tf.float32))

    self.assertAllEqual(
        counterfactual.node_sets["node"].features["h"],
        tf.constant((6295.455, 3710.2205, 5127.05), dtype=tf.float32))

  def test_counterfactual_zeros(self):
    counterfactual = attribution.counterfactual(self.gt, random=False)

    self.assertAllEqual(
        counterfactual.context.features["h"],
        tf.constant((0, 0), dtype=tf.float32))

    self.assertAllEqual(
        counterfactual.edge_sets["edge"].features["weight"],
        tf.constant((0, 0), dtype=tf.float32))

    self.assertAllEqual(
        counterfactual.node_sets["node"].features["h"],
        tf.constant((0, 0, 0), dtype=tf.float32))

  def test_subtract_graph_features(self):
    deltas = attribution.subtract_graph_features(
        self.gt,
        self.gt.replace_features(
            context={"h": tf.constant((4, 8), dtype=tf.float32)},
            node_sets={
                "node": {
                    "h": tf.constant((1, 2, 3), dtype=tf.float32)
                }
            },
            edge_sets={
                "edge": {
                    "weight": tf.constant((2, 1), dtype=tf.float32)
                }
            }))

    self.assertAllEqual(
        deltas.context.features["h"],
        tf.constant((514 - 4, 433 - 8), dtype=tf.float32))

    self.assertAllEqual(
        deltas.edge_sets["edge"].features["weight"],
        tf.constant((153 - 2, 9 - 1), dtype=tf.float32))

    self.assertAllEqual(
        deltas.node_sets["node"].features["h"],
        tf.constant((8191 - 1, 9474 - 2, 1634 - 3), dtype=tf.float32))

  def test_interpolate(self):
    counterfactual = attribution.counterfactual(self.gt, random=True, seed=8191)
    interpolations = attribution.interpolate_graph_features(
        self.gt,
        counterfactual,
        steps=4)

    self.assertLen(interpolations, 4)

    # Interpolation 0
    self.assertAllEqual(
        interpolations[0].context.features["h"],
        tf.constant((492.80963, 466.38303), dtype=tf.float32))

    self.assertAllEqual(
        interpolations[0].edge_sets["edge"].features["weight"],
        tf.constant((134.47087, 66.30827), dtype=tf.float32))

    self.assertAllClose(
        interpolations[0].node_sets["node"].features["h"],
        tf.constant((6295.455, 3710.2205, 5127.05), dtype=tf.float32))

    # Interpolation 1
    self.assertAllEqual(
        interpolations[1].context.features["h"],
        tf.constant((492.80963 + (514 - 492.80963) * 1 / 3,
                     466.38303 + (433 - 466.38303) * 1 / 3),
                    dtype=tf.float32))

    self.assertAllClose(
        interpolations[1].edge_sets["edge"].features["weight"],
        tf.constant((134.47087 + (153 - 134.47087) * 1 / 3,
                     66.30827 + (9 - 66.30827) * 1 / 3),
                    dtype=tf.float32))

    self.assertAllClose(
        interpolations[1].node_sets["node"].features["h"],
        tf.constant((6295.455 + (8191 - 6295.455) * 1 / 3,
                     3710.2205 + (9474 - 3710.2205) * 1 / 3,
                     5127.05 + (1634 - 5127.05) * 1 / 3),
                    dtype=tf.float32))

    # Interpolation 2
    self.assertAllEqual(
        interpolations[2].context.features["h"],
        tf.constant((492.80963 + (514 - 492.80963) * 2 / 3,
                     466.38303 + (433 - 466.38303) * 2 / 3),
                    dtype=tf.float32))

    self.assertAllClose(
        interpolations[2].edge_sets["edge"].features["weight"],
        tf.constant((134.47087 + (153 - 134.47087) * 2 / 3,
                     66.30827 + (9 - 66.30827) * 2 / 3),
                    dtype=tf.float32))

    self.assertAllClose(
        interpolations[2].node_sets["node"].features["h"],
        tf.constant((6295.455 + (8191 - 6295.455) * 2 / 3,
                     3710.2205 + (9474 - 3710.2205) * 2 / 3,
                     5127.05 + (1634 - 5127.05) * 2 / 3),
                    dtype=tf.float32))

    # Interpolation 3
    self.assertAllEqual(
        interpolations[3].context.features["h"],
        tf.constant((514, 433), dtype=tf.float32))

    self.assertAllEqual(
        interpolations[3].edge_sets["edge"].features["weight"],
        tf.constant((153, 9), dtype=tf.float32))

    self.assertAllEqual(
        interpolations[3].node_sets["node"].features["h"],
        tf.constant((8191, 9474, 1634), dtype=tf.float32))

  def test_sum_graph_features(self):
    summation = attribution.sum_graph_features((self.gt,) * 4)

    self.assertAllEqual(
        summation.context.features["h"],
        tf.constant((514 * 4, 433 * 4), dtype=tf.float32))

    self.assertAllEqual(
        summation.edge_sets["edge"].features["weight"],
        tf.constant((153 * 4, 9 * 4), dtype=tf.float32))

    self.assertAllEqual(
        summation.node_sets["node"].features["h"],
        tf.constant((8191 * 4, 9474 * 4, 1634 * 4), dtype=tf.float32))

  def test_integrated_gradients_exporter(self):
    examples = tf.keras.Input(shape=(), dtype=tf.string, name="examples")
    parsed = tfgnn.keras.layers.ParseExample(self.gt.spec)(examples)
    parsed = parsed.merge_batch_to_components()
    labels = parsed.context["h"][0]

    preprocess_model = tf.keras.Model(examples, (parsed, labels))

    inputs = tf.keras.Input(type_spec=self.gt.spec)
    graph = inputs.merge_batch_to_components()

    values = tfgnn.broadcast_node_to_edges(
        graph,
        "edge",
        tfgnn.TARGET,
        feature_name="h")[:, None]
    weights = graph.edge_sets["edge"].features["weight"][:, None]

    messages = tf.keras.layers.Concatenate()((values, weights))
    messages = tf.keras.layers.Dense(16)(messages)

    pooled = tfgnn.pool_edges_to_node(
        graph,
        "edge",
        tfgnn.SOURCE,
        reduce_type="sum",
        feature_value=messages)

    h_old = graph.node_sets["node"].features["h"][:, None]
    h_next = tf.keras.layers.Concatenate()((pooled, h_old))
    h_next = tf.keras.layers.Dense(1)(h_next)
    graph = graph.replace_features(node_sets={"node": {"h": h_next}})

    activations = tfgnn.keras.layers.ReadoutFirstNode(
        node_set_name="node",
        feature_name="h")(graph)

    model = tf.keras.Model(inputs, activations)
    model.compile("adam", "mae")

    export_dir = self.create_tempdir()
    exporter = attribution.IntegratedGradientsExporter("output", steps=3)
    exporter.save(preprocess_model, model, export_dir)

    saved_model = tf.saved_model.load(export_dir)

    example = tfgnn.write_example(self.gt)
    kwargs = {
        "examples": tf.constant((example.SerializeToString(),))
    }
    outputs = saved_model.signatures["integrated_gradients"](**kwargs)
    gt = outputs["output"]

    # The above GNN passes a single message over the only edge type before
    # collecting a seed node for activations. The above graph is a line:
    # seed --weight 0--> node 1 --weight 1--> node 2.
    #
    # Information from weight 1 and node 2 never reaches the activations: they
    # should see no integrated gradients.
    self.assertAllClose(
        gt.node_sets["node"].features["h"],
        tf.constant((0.992285, 1.659444, 0.), dtype=tf.float32))

    self.assertAllClose(
        gt.edge_sets["edge"].features["weight"],
        tf.constant((0.641726, 0.), dtype=tf.float32))

  def test_protocol(self):
    self.assertIsInstance(IntegratedGradientsExporter, ModelExporter)


if __name__ == "__main__":
  tf.test.main()
