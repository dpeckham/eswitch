// Native implementation of route_gaps.py's four-neighbor A* search.
// All geometry and every accepted route remain checked by KiCad DRC.
#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <limits>
#include <queue>
#include <vector>
struct Entry { int f, g, node; };
struct Greater { bool operator()(const Entry&a,const Entry&b) const {
  if(a.f!=b.f)return a.f>b.f;
  if(a.g!=b.g)return a.g>b.g;
  return a.node>b.node;
}};
extern "C" int grid_search(int nx,int ny,const uint8_t* blocked,const uint8_t* via,
 const int32_t* starts,int ns,const int32_t* goals,int ng,int32_t* output,int capacity) {
 const int size=nx*ny,total=3*size;
 std::vector<int> dist(total,std::numeric_limits<int>::max()),parent(total,-1);
 std::vector<uint8_t> target(total,0);
 int x0=nx,y0=ny,x1=0,y1=0;
 for(int k=0;k<ng;k++){int n=goals[k],loc=n%size,x=loc%nx,y=loc/nx;
  target[n]=1;x0=std::min(x0,x);x1=std::max(x1,x);y0=std::min(y0,y);y1=std::max(y1,y);}
 auto estimate=[&](int n){int loc=n%size,x=loc%nx,y=loc/nx;
  return std::max({x0-x,0,x-x1})+std::max({y0-y,0,y-y1});};
 std::priority_queue<Entry,std::vector<Entry>,Greater> queue;
 for(int k=0;k<ns;k++){int n=starts[k];dist[n]=0;queue.push({estimate(n),0,n});}
 while(!queue.empty()){
  auto e=queue.top();queue.pop();int n=e.node,g=e.g;
  if(g>dist[n])continue;
  if(target[n]){std::vector<int> path;for(int at=n;at!=-1;at=parent[at])path.push_back(at);
   if(int(path.size())>capacity)return -1;
   std::reverse(path.begin(),path.end());std::copy(path.begin(),path.end(),output);return path.size();}
  int plane=n/size,loc=n%size,x=loc%nx,y=loc/nx;
  auto visit=[&](int next,int delta){int cost=g+delta;if(!blocked[next]&&cost<dist[next]){
   dist[next]=cost;parent[next]=n;queue.push({cost+estimate(next),cost,next});}};
  if(x)visit(n-1,1);if(x+1<nx)visit(n+1,1);if(y)visit(n-nx,1);if(y+1<ny)visit(n+nx,1);
  if(!via[loc])for(int other=0;other<3;other++)if(other!=plane)visit(other*size+loc,35);
 }
 return 0;
}
