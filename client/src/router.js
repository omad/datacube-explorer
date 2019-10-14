import Vue from 'vue';
import Router from 'vue-router';
// import Home from './views/Home.vue';
import Ping from './components/Ping.vue';
import Products from './components/Products.vue';
import ProductSummary from './components/ProductSummary.vue';

Vue.use(Router);

export default new Router({
  mode: 'history',
  base: process.env.BASE_URL,
  routes: [
    {
      path: '/ping',
      name: 'ping',
      component: Ping,
    },
    {
      path: '/products',
      name: 'products',
      component: Products,
    },
    {
      path: '/:productid',
      name: 'productsummary',
      component: ProductSummary,
    },
    {
      path: '/about',
      name: 'about',
      // route level code-splitting
      // this generates a separate chunk (about.[hash].js) for this route
      // which is lazy-loaded when the route is visited.
      component: () => import(/* webpackChunkName: "about" */ './views/About.vue'),
    },
  ],
});
