<template>
  <div class="container">
    <div class="row">
      <div class="col-sm-10">
        <h1>Products</h1>
        <hr><br><br>
        <table class="table table-hover">
          <thead>
          <tr>
            <th scope="col">Title</th>
            <th scope="col">Description</th>
          </tr>
          </thead>
          <tbody>
          <tr v-for="(product, index) in products" :key="index">
            <td><router-link :to="{ name: 'productsummary', params: { productid: product.title }}">
              {{ product.title }}</router-link>
            </td>
            <td><router-link to="ping">{{ product.description }}</router-link></td>
          </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
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
