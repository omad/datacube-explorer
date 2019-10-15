<template>
  <div class="container">
    <div v-if="loading">Loading...</div>
    {{ product }}
  </div>
</template>

<script>
import axios from 'axios';

export default {
  name: 'ProductSummary',
  data() {
    return {
      product: undefined,
      loading: true,
    };
  },
  created() {
    // fetch the data when the view is created and the data is
    // already being observed
    this.fetchData();
  },
  watch: {
    // call again the method if the route changes
    $route: 'fetchData',
  },
  methods: {
    fetchData() {
      this.product = undefined;
      this.loading = true;
      const path = `http://localhost:5000/collections/${this.$route.params.productid}`;
      axios.get(path)
        .then((res) => {
          this.product = res.data;
        })
        .catch((error) => {
          // eslint-disable-next-line
          console.error(error);
        })
        .finally(() => {
          this.loading = false;
        });
    },
  },
};
</script>
