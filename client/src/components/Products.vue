<template>
  <ul>
    <li v-for="(product, index) in products" :key="index">
      <router-link :to="{ name: 'productsummary', params: { productid: product.title }}"
        :title="product.description">
        {{ product.title }}</router-link>
    </li>
  </ul>
</template>

<script>
import axios from 'axios';

export default {
  name: 'Products',
  data() {
    return {
      products: [],
    };
  },
  methods: {
    getProducts() {
      const path = 'http://localhost:5000/stac';
      axios.get(path)
        .then((res) => {
          this.products = res.data.links;
        })
        .catch((error) => {
          // eslint-disable-next-line
          console.error(error);
        });
    },
  },
  created() {
    this.getProducts();
  },
};
</script>
